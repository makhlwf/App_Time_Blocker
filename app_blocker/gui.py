import wx
import wx.adv # For TaskBarIcon
import os
import sys # Ensure sys is imported for path adjustments
import ctypes # For admin check and re-launch
import datetime
import threading
import time # Keep for any direct time usage, though blocker handles its own loop timing
import gettext

# --- Language Setup ---
def get_bundle_dir_gui():
    """ Returns the base directory for PyInstaller bundle or script directory for normal execution. """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running in a normal Python environment
        # Assumes gui.py is in app_blocker, and project root is one level up.
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

GUI_LOCALE_DIR = os.path.join(get_bundle_dir_gui(), 'locale')

# Global `_` function, initialized to default gettext
_ = gettext.gettext

def set_language(lang_code='en'):
    """Sets the language for the GUI module."""
    global _
    if os.path.isdir(GUI_LOCALE_DIR):
        try:
            translation = gettext.translation('messages', localedir=GUI_LOCALE_DIR, languages=[lang_code], fallback=True)
            _ = translation.gettext
        except Exception as e:
            print(f"Failed to set language to {lang_code} in gui.py: {e}. Using fallback gettext.")
            _ = gettext.gettext # Fallback to basic gettext
    else:
        print(f"Locale directory '{GUI_LOCALE_DIR}' not found in gui.py. Using fallback gettext.")
        _ = gettext.gettext # Fallback if locale directory isn't found

# Initialize with a default language (e.g., 'en'). 
# AppBlockerFrame will call this again with the configured language.
set_language() 

# Import from our new modules
from .config import (
    CONFIG_FILE_PATH, TRAY_ICON_PATH,
    load_config_from_file, save_config_to_file
)
from .blocker import monitor_loop # Import the refactored monitor_loop

class AppTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame, tooltip_text): 
        super(AppTaskBarIcon, self).__init__()
        self.frame = frame

        # Set Icon
        try:
            if os.path.exists(TRAY_ICON_PATH): 
                icon = wx.Icon(TRAY_ICON_PATH, wx.BITMAP_TYPE_PNG)
            else: 
                icon = wx.Icon(wx.STOCK_ICON_APPLICATION)
            self.SetIcon(icon, tooltip_text) 
        except Exception as e:
            print(f"Error setting tray icon: {e}. Using default.")
            try:
                std_icon = wx.Icon()
                std_icon.CopyFromBitmap(wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_TOOLBAR, (16,16)))
                self.SetIcon(std_icon, tooltip_text) 
            except Exception as e_std:
                print(f"Error setting standard tray icon: {e_std}")

        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.EVT_MENU, self.on_show_hide, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_exit_app, id=wx.ID_EXIT)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        menu.Append(wx.ID_OPEN, _("Show/Hide App"))
        menu.AppendSeparator()
        menu.Append(wx.ID_EXIT, _("Exit Blocker"))
        return menu

    def on_left_dclick(self, event):
        self.frame.toggle_visibility()

    def on_show_hide(self, event):
        self.frame.toggle_visibility()

    def on_exit_app(self, event):
        self.frame.on_proper_exit()

    def cleanup(self):
        self.Unbind(wx.adv.EVT_TASKBAR_LEFT_DCLICK)
        self.Unbind(wx.EVT_MENU, id=wx.ID_OPEN)
        self.Unbind(wx.EVT_MENU, id=wx.ID_EXIT)
        if not self.IsBeingDeleted(): 
            self.Destroy()


class AppBlockerFrame(wx.Frame):
    def __init__(self, parent, title, tray_tooltip_text, current_lang='en'): # Added current_lang
        
        self.current_lang = current_lang # Store language
        set_language(self.current_lang) # Set language for GUI module

        super(AppBlockerFrame, self).__init__(parent, title=title, size=(600, 700)) # Increased height for lang menu

        # Configuration attributes
        self.app_path_val = ""
        self.end_hour_val = 17
        self.end_minute_val = 0
        self.block_activated_today = False
        self.date_block_activated = None
        # self.current_lang is already set

        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()

        self.taskBarIcon = None
        self.tray_tooltip_text = tray_tooltip_text 

        self._load_initial_config() # This will load language too, and self.current_lang will be updated
                                    # then we must re-set the language for the GUI
        set_language(self.current_lang) # Re-set language based on loaded config

        self.InitUI() 
        self.Centre()
        self.Show()

        self.Bind(wx.EVT_CLOSE, self.on_minimize_to_tray)
        self.Bind(wx.EVT_ICONIZE, self.on_iconize_to_tray)

        if not self.is_admin():
            self._prompt_for_admin_restart()
        
        self.log_status(_("Idle. Configure and start monitoring."))
        if os.path.exists(CONFIG_FILE_PATH): # This path is for data, not translation
             self.log_status(_("Configuration loaded from {config_path}").format(config_path=CONFIG_FILE_PATH))
        else:
             self.log_status(_("No prior configuration found. Using defaults."))
        
        self.setup_taskbar_icon() # Ensure it's called after tray_tooltip_text is set


    def setup_taskbar_icon(self):
        if not self.taskBarIcon:
            self.taskBarIcon = AppTaskBarIcon(self, self.tray_tooltip_text) # Pass it here

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError: 
            print(_("Admin check: ctypes.windll.shell32 not available. Assuming not admin."))
            return False
        except Exception as e:
            self.log_status(_("Error checking admin status: {error}").format(error=e))
            return False
            
    def _prompt_for_admin_restart(self):
        dlg = wx.MessageDialog(self,
                               _("This application may not function correctly without Administrator privileges "
                                 "(e.g., terminating other admin-level apps).\n\n"
                                 "Would you like to try restarting it as Administrator?"),
                               _("Administrator Privileges Recommended"),
                               wx.YES_NO | wx.ICON_WARNING)
        if dlg.ShowModal() == wx.ID_YES:
            self.restart_as_admin()
        dlg.Destroy()

    def restart_as_admin(self):
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([script] + sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            self.on_proper_exit(is_restarting=True) 
        except Exception as e:
            wx.MessageBox(_("Failed to restart as admin: {error}").format(error=e), _("Error"), wx.OK | wx.ICON_ERROR)
            self.log_status(_("Admin restart failed: {error}").format(error=e))

    def InitUI(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Application Path Section
        path_box = wx.StaticBox(panel, label=_("Application Settings"))
        path_box_sizer = wx.StaticBoxSizer(path_box, wx.VERTICAL)
        grid_sizer = wx.GridBagSizer(5, 5)

        lbl_app = wx.StaticText(panel, label=_("Application to Block:"))
        grid_sizer.Add(lbl_app, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        self.txt_app_path = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.txt_app_path.SetValue(self.app_path_val) # Loaded from config
        grid_sizer.Add(self.txt_app_path, pos=(0, 1), span=(1,1), flag=wx.EXPAND)
        btn_browse = wx.Button(panel, label=_("Browse..."))
        btn_browse.Bind(wx.EVT_BUTTON, self.on_browse_app)
        grid_sizer.Add(btn_browse, pos=(0, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)

        lbl_time = wx.StaticText(panel, label=_("Block After (HH:MM):"))
        grid_sizer.Add(lbl_time, pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        time_input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.spin_hour = wx.SpinCtrl(panel, value=str(self.end_hour_val), min=0, max=23, size=(50,-1))
        self.spin_minute = wx.SpinCtrl(panel, value=str(self.end_minute_val), min=0, max=59, size=(50,-1))
        time_input_sizer.Add(self.spin_hour, 0, wx.RIGHT, 5)
        time_input_sizer.Add(wx.StaticText(panel, label=":"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5) # Not typically translated
        time_input_sizer.Add(self.spin_minute, 0)
        grid_sizer.Add(time_input_sizer, pos=(1, 1), flag=wx.ALIGN_LEFT)
        grid_sizer.AddGrowableCol(1)
        path_box_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(path_box_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Controls Section
        control_box = wx.StaticBox(panel, label=_("Controls"))
        control_box_sizer = wx.StaticBoxSizer(control_box, wx.HORIZONTAL)
        self.btn_start = wx.Button(panel, label=_("Start Monitoring"))
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start_monitoring)
        control_box_sizer.Add(self.btn_start, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.btn_stop = wx.Button(panel, label=_("Stop Monitoring"))
        self.btn_stop.Bind(wx.EVT_BUTTON, self.on_stop_monitoring)
        control_box_sizer.Add(self.btn_stop, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        main_sizer.Add(control_box_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Status Log Section
        status_box = wx.StaticBox(panel, label=_("Status Log"))
        status_box_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        self.txt_status_log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 150))
        status_box_sizer.Add(self.txt_status_log, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(status_box_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(main_sizer)
        self.update_ui_for_monitoring_state()

    def log_status(self, message): # message should be pre-translated if it's a translatable one
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{now_str}] {message}\n" # Date format is not typically translated
        if hasattr(self, 'txt_status_log') and self.txt_status_log:
            # Ensure this runs on the main GUI thread
            if wx.IsMainThread():
                self.txt_status_log.AppendText(full_message)
            else:
                wx.CallAfter(self.txt_status_log.AppendText, full_message)
        print(full_message.strip()) # For console debugging, not translated

    def on_browse_app(self, event):
        if self.monitoring_active:
            wx.MessageBox(_("Stop monitoring before changing settings."), _("Warning"), wx.OK | wx.ICON_WARNING, self)
            return
        # FileDialog's title and wildcard are standard OS dialogs, often system-translated.
        # We provide our desired default title and wildcard.
        with wx.FileDialog(self, _("Select Application"), wildcard=_("Executable files (*.exe)|*.exe|All files (*.*)|*.*"),
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            self.app_path_val = fileDialog.GetPath()
            self.txt_app_path.SetValue(self.app_path_val)
            self.log_status(_("Selected application: {app_path}").format(app_path=self.app_path_val))
            # Save config immediately after path change if not monitoring
            self._save_current_config()


    def _load_initial_config(self):
        config = load_config_from_file()
        self.app_path_val = config["app_path"]
        self.end_hour_val = config["end_hour"]
        self.end_minute_val = config["end_minute"]
        self.block_activated_today = config["block_activated_today"]
        self.date_block_activated = config["date_block_activated"]
        # Log statements about config loading are in __init__ or handled by load_config_from_file itself for console.

    def _save_current_config(self):
        # Get current values from UI controls if they exist, otherwise use stored values
        current_hour = self.spin_hour.GetValue() if hasattr(self, 'spin_hour') and self.spin_hour else self.end_hour_val
        current_minute = self.spin_minute.GetValue() if hasattr(self, 'spin_minute') and self.spin_minute else self.end_minute_val
        
        save_config_to_file(
            self.app_path_val,
            current_hour,
            current_minute,
            self.block_activated_today,
            self.date_block_activated
        )
        self.log_status(_("Configuration saved."))

    def update_ui_for_monitoring_state(self):
        is_monitoring = self.monitoring_active
        if hasattr(self, 'btn_start'): # Ensure UI elements exist
            self.btn_start.Enable(not is_monitoring)
            self.btn_stop.Enable(is_monitoring)
            
            # Find the browse button correctly. self.GetChildren()[0] is the panel.
            panel = self.GetChildren()[0]
            browse_button = wx.FindWindowByLabel("Browse...", parent=panel)
            if browse_button: browse_button.Enable(not is_monitoring)

            self.spin_hour.Enable(not is_monitoring)
            self.spin_minute.Enable(not is_monitoring)

    # --- Callbacks for monitor_loop ---
    def get_block_state(self):
        return self.block_activated_today, self.date_block_activated

    def set_block_state_and_save(self, block_activated, date_activated):
        self.block_activated_today = block_activated
        self.date_block_activated = date_activated
        self._save_current_config() # This now saves the state passed from the blocker thread

    def on_monitoring_stopped_by_thread(self):
        """Called by monitor_loop (via wx.CallAfter) when it stops unexpectedly or finishes."""
        if self.monitoring_active: # If it was stopped by an error in the thread
            self.monitoring_active = False
            self.log_status(_("Monitoring stopped unexpectedly by the monitoring thread."))
        # self.stop_event should already be set if stop was graceful
        self.update_ui_for_monitoring_state()
        # Ensure thread object is cleared
        self.monitor_thread = None
    # --- End Callbacks ---

    def on_start_monitoring(self, event):
        if not self.app_path_val:
            wx.MessageBox(_("Please select an application to block."), _("Error"), wx.OK | wx.ICON_ERROR, self)
            return

        self.end_hour_val = self.spin_hour.GetValue()
        self.end_minute_val = self.spin_minute.GetValue()

        self.monitoring_active = True
        self.stop_event.clear()
        self._save_current_config() # Save current settings before starting
        self.update_ui_for_monitoring_state()

        # Most log messages in monitor_loop itself are for debugging or specific events,
        # but the initial start message can be translated here.
        app_name = os.path.basename(self.app_path_val) if self.app_path_val else _("N/A")
        self.log_status(_("Monitoring started for {app_name}. Block after {hour:02d}:{minute:02d}.").format(
            app_name=app_name, hour=self.end_hour_val, minute=self.end_minute_val
        ))

        self.monitor_thread = threading.Thread(
            target=monitor_loop,
            args=(
                self.app_path_val,
                self.end_hour_val,
                self.end_minute_val,
                self.stop_event,
                self.get_block_state,         # Pass callback for getting state
                self.set_block_state_and_save,# Pass callback for setting state & saving
                self.log_status,              # Pass logging callback
                wx.CallAfter,                 # Pass wx.CallAfter for thread-safe GUI calls
                self.on_monitoring_stopped_by_thread # Callback for when thread stops
            ),
            daemon=True
        )
        self.monitor_thread.start()
        # The log message was moved up to be translatable before thread start.

    def on_stop_monitoring(self, event=None): # event can be None if called internally
        if self.monitoring_active:
            self.log_status(_("Stop monitoring signal sent..."))
            self.monitoring_active = False # Optimistically set, will be confirmed by thread callback
            self.stop_event.set()
            # Don't join here, it can freeze UI. Let thread stop and call back.
        else:
            # If already stopped or stopping, ensure UI is consistent
            self.update_ui_for_monitoring_state()
            self.log_status(_("Monitoring is not active or already stopping."))


    def toggle_visibility(self):
        if self.IsShown():
            self.Hide()
        else:
            self.Show()
            self.Raise() 

    def on_minimize_to_tray(self, event):
        if isinstance(event, wx.CloseEvent): 
            self.Hide()
            # Do not Veto if you want default system tray icon behavior on some platforms.
            # However, for consistent "minimize to tray", Hide() is key.
            # event.Veto() # This might be needed if just Hide() is not enough
        elif isinstance(event, wx.IconizeEvent):
            if event.IsIconized():
                self.Hide()

    def on_iconize_to_tray(self, event): # This is bound to EVT_ICONIZE
        if event.IsIconized():
            self.Hide()

    def on_proper_exit(self, event=None, is_restarting=False):
        self.log_status(_("Exiting application..."))
        if self.monitoring_active:
            self.stop_event.set() # Signal thread to stop
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.log_status(_("Waiting for monitor thread to finish..."))
                self.monitor_thread.join(timeout=2) 
                if self.monitor_thread.is_alive():
                    self.log_status(_("Monitor thread did not finish in time."))
            self.monitoring_active = False # Ensure state is updated

        if not is_restarting:
            self._save_current_config() # Save final state

        if self.taskBarIcon:
            self.taskBarIcon.cleanup()
            self.taskBarIcon = None
        
        # wx.CallAfter(self.Destroy) # Safely destroy the frame
        self.Destroy() # Direct destroy might be okay if all threads handled
        # wx.GetApp().ExitMainLoop() # Might be needed if Destroy() alone doesn't exit.
                                   # Typically wx.App exits when its top window is destroyed.

# Note: The if __name__ == '__main__': block will be in the new app_blocker/main.py
# This gui.py file will only contain the class definitions and their imports.
