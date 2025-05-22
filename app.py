import wx
import wx.adv # For TaskBarIcon
import psutil
import datetime
import threading
import time
import json
import os
import sys
import ctypes # For admin check and re-launch

# --- Configuration ---
CONFIG_FILE_NAME = "app_blocker_config_wx_v2.json"
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "AppBlockerWxV2")
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)
CONFIG_FILE_PATH = os.path.join(APP_DATA_DIR, CONFIG_FILE_NAME)

TRAY_TOOLTIP = 'App Time Blocker'
TRAY_ICON_PATH = "icon.png" # Create a small 16x16 or 32x32 png icon named icon.png in the same dir, or use wx.Icon.GetStdIcon

class AppTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super(AppTaskBarIcon, self).__init__()
        self.frame = frame

        # Set Icon
        try:
            if os.path.exists(TRAY_ICON_PATH):
                icon = wx.Icon(TRAY_ICON_PATH, wx.BITMAP_TYPE_PNG)
            else: # Fallback to a standard icon
                icon = wx.Icon(wx.STOCK_ICON_APPLICATION) # Or any other wx.STOCK_ICON_*
            self.SetIcon(icon, TRAY_TOOLTIP)
        except Exception as e:
            print(f"Error setting tray icon: {e}. Using default.")
            # Fallback if custom icon fails
            try:
                std_icon = wx.Icon()
                std_icon.CopyFromBitmap(wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_TOOLBAR, (16,16)))
                self.SetIcon(std_icon, TRAY_TOOLTIP)
            except Exception as e_std:
                print(f"Error setting standard tray icon: {e_std}")


        # Bindings
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.EVT_MENU, self.on_show_hide, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_exit_app, id=wx.ID_EXIT)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        menu.Append(wx.ID_OPEN, "Show/Hide App")
        menu.AppendSeparator()
        menu.Append(wx.ID_EXIT, "Exit Blocker")
        return menu

    def on_left_dclick(self, event):
        self.frame.toggle_visibility()

    def on_show_hide(self, event):
        self.frame.toggle_visibility()

    def on_exit_app(self, event):
        self.frame.on_proper_exit()

    def cleanup(self):
        # This method is called by the frame before destroying the taskbar icon
        # It ensures that no methods are called on a destroyed taskbar icon
        self.Unbind(wx.adv.EVT_TASKBAR_LEFT_DCLICK)
        self.Unbind(wx.EVT_MENU, id=wx.ID_OPEN)
        self.Unbind(wx.EVT_MENU, id=wx.ID_EXIT)
        self.Destroy() # Important to destroy the taskbar icon object itself


class AppBlockerFrame(wx.Frame):
    def __init__(self, parent, title):
        super(AppBlockerFrame, self).__init__(parent, title=title, size=(600, 650)) # Adjusted size slightly

        self.app_path_val = ""
        self.end_hour_val = 17
        self.end_minute_val = 0

        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()

        self.block_activated_today = False
        self.date_block_activated = None

        self.taskBarIcon = None # Initialize taskbar icon reference

        self.load_config()
        self.InitUI()
        self.Centre()
        # self.Show() # Will be shown/hidden via taskbar or explicitly

        self.Bind(wx.EVT_CLOSE, self.on_minimize_to_tray) # Change close button behavior
        self.Bind(wx.EVT_ICONIZE, self.on_iconize_to_tray)

        # Show initially if not hidden by default logic
        # For testing, let's show it. Later, you might want to start minimized.
        self.Show()
        self.setup_taskbar_icon()


        if not self.is_admin():
            dlg = wx.MessageDialog(self,
                                   "This application may not function correctly without Administrator privileges "
                                   " (e.g., terminating other admin-level apps).\n\n"
                                   "Would you like to try restarting it as Administrator?",
                                   "Administrator Privileges Recommended",
                                   wx.YES_NO | wx.ICON_WARNING)
            if dlg.ShowModal() == wx.ID_YES:
                self.restart_as_admin()
            dlg.Destroy()

        # Initial status log
        self.log_status("Idle. Configure and start monitoring.")
        if os.path.exists(CONFIG_FILE_PATH):
             self.log_status(f"Configuration loaded from {CONFIG_FILE_PATH}")
        else:
             self.log_status("No prior configuration found. Using defaults.")


    def setup_taskbar_icon(self):
        if not self.taskBarIcon:
            self.taskBarIcon = AppTaskBarIcon(self)

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def restart_as_admin(self):
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([script] + sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            self.on_proper_exit(is_restarting=True) # Close current instance
        except Exception as e:
            wx.MessageBox(f"Failed to restart as admin: {e}", "Error", wx.OK | wx.ICON_ERROR)
            self.log_status(f"Admin restart failed: {e}")


    def InitUI(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Application Path Section ---
        path_box = wx.StaticBox(panel, label="Application Settings")
        path_box_sizer = wx.StaticBoxSizer(path_box, wx.VERTICAL)
        grid_sizer = wx.GridBagSizer(5, 5)

        lbl_app = wx.StaticText(panel, label="Application to Block:")
        grid_sizer.Add(lbl_app, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        self.txt_app_path = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.txt_app_path.SetValue(self.app_path_val)
        grid_sizer.Add(self.txt_app_path, pos=(0, 1), span=(1,1), flag=wx.EXPAND)
        btn_browse = wx.Button(panel, label="Browse...")
        btn_browse.Bind(wx.EVT_BUTTON, self.on_browse_app)
        grid_sizer.Add(btn_browse, pos=(0, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)

        lbl_time = wx.StaticText(panel, label="Block After (HH:MM):")
        grid_sizer.Add(lbl_time, pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)
        time_input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.spin_hour = wx.SpinCtrl(panel, value=str(self.end_hour_val), min=0, max=23, size=(50,-1))
        self.spin_minute = wx.SpinCtrl(panel, value=str(self.end_minute_val), min=0, max=59, size=(50,-1))
        time_input_sizer.Add(self.spin_hour, 0, wx.RIGHT, 5)
        time_input_sizer.Add(wx.StaticText(panel, label=":"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        time_input_sizer.Add(self.spin_minute, 0)
        grid_sizer.Add(time_input_sizer, pos=(1, 1), flag=wx.ALIGN_LEFT)
        grid_sizer.AddGrowableCol(1)
        path_box_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(path_box_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Controls Section ---
        control_box = wx.StaticBox(panel, label="Controls")
        control_box_sizer = wx.StaticBoxSizer(control_box, wx.HORIZONTAL)
        self.btn_start = wx.Button(panel, label="Start Monitoring")
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start_monitoring)
        control_box_sizer.Add(self.btn_start, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.btn_stop = wx.Button(panel, label="Stop Monitoring")
        self.btn_stop.Bind(wx.EVT_BUTTON, self.on_stop_monitoring)
        control_box_sizer.Add(self.btn_stop, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        main_sizer.Add(control_box_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # --- Status Log Section ---
        status_box = wx.StaticBox(panel, label="Status Log")
        status_box_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        self.txt_status_log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 150))
        status_box_sizer.Add(self.txt_status_log, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(status_box_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # --- Important Considerations (text from previous version) ---
        # You can keep this if you still want the text displayed, or remove if features are enough
        # For brevity in this revision, I'll comment it out, assuming features are preferred
        # info_box = wx.StaticBox(panel, label="Important Information")
        # ... (rest of the info_box code if you keep it)
        # main_sizer.Add(info_box_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(main_sizer)
        self.update_ui_for_monitoring_state()

    def log_status(self, message):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{now_str}] {message}\n"
        if hasattr(self, 'txt_status_log') and self.txt_status_log:
            wx.CallAfter(self.txt_status_log.AppendText, full_message)
        print(full_message.strip())

    def on_browse_app(self, event):
        if self.monitoring_active:
            wx.MessageBox("Stop monitoring before changing settings.", "Warning", wx.OK | wx.ICON_WARNING, self)
            return
        with wx.FileDialog(self, "Select Application", wildcard="Executable files (*.exe)|*.exe|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            self.app_path_val = fileDialog.GetPath()
            self.txt_app_path.SetValue(self.app_path_val)
            self.log_status(f"Selected application: {self.app_path_val}")

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, "r") as f:
                    config = json.load(f)
                    self.app_path_val = config.get("app_path", "")
                    self.end_hour_val = int(config.get("end_hour", 17))
                    self.end_minute_val = int(config.get("end_minute", 0))

                    # *** TIME BUG FIX: Crucial logic for loading block state ***
                    loaded_block_activated = config.get("block_activated_today", False)
                    date_str = config.get("date_block_activated", None)
                    
                    if loaded_block_activated and date_str:
                        saved_block_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                        if saved_block_date == datetime.date.today():
                            # Block was activated today and is still relevant
                            self.block_activated_today = True
                            self.date_block_activated = saved_block_date
                        elif saved_block_date < datetime.date.today():
                            # Block was for a previous day, so reset
                            self.block_activated_today = False
                            self.date_block_activated = None
                        # else: saved_block_date > today (future date, shouldn't happen, treat as not blocked)
                        #    self.block_activated_today = False
                        #    self.date_block_activated = None
                    else:
                        # If no valid date or not activated, ensure it's reset
                        self.block_activated_today = False
                        self.date_block_activated = None
            # self.log_status("Configuration loaded.") # Logged after UI init
        except Exception as e:
            self.log_status(f"Error loading config: {e}. Using defaults.")
            self.app_path_val = ""
            self.end_hour_val = 17
            self.end_minute_val = 0
            self.block_activated_today = False
            self.date_block_activated = None

    def save_config(self):
        current_hour = self.spin_hour.GetValue() if hasattr(self, 'spin_hour') else self.end_hour_val
        current_minute = self.spin_minute.GetValue() if hasattr(self, 'spin_minute') else self.end_minute_val

        config = {
            "app_path": self.app_path_val,
            "end_hour": current_hour,
            "end_minute": current_minute,
            "block_activated_today": self.block_activated_today,
            "date_block_activated": self.date_block_activated.isoformat() if self.date_block_activated else None
        }
        try:
            with open(CONFIG_FILE_PATH, "w") as f:
                json.dump(config, f, indent=4)
            self.log_status("Configuration saved.")
        except Exception as e:
            self.log_status(f"Error saving config: {e}")

    def update_ui_for_monitoring_state(self):
        is_monitoring = self.monitoring_active
        if hasattr(self, 'btn_start'): # Ensure UI elements exist
            self.btn_start.Enable(not is_monitoring)
            self.btn_stop.Enable(is_monitoring)
            
            browse_button = wx.FindWindowByLabel("Browse...", parent=self.GetChildren()[0])
            if browse_button: browse_button.Enable(not is_monitoring)

            self.spin_hour.Enable(not is_monitoring)
            self.spin_minute.Enable(not is_monitoring)

    def on_start_monitoring(self, event):
        if not self.app_path_val:
            wx.MessageBox("Please select an application to block.", "Error", wx.OK | wx.ICON_ERROR, self)
            return

        self.end_hour_val = self.spin_hour.GetValue()
        self.end_minute_val = self.spin_minute.GetValue()

        self.monitoring_active = True
        self.stop_event.clear()
        self.update_ui_for_monitoring_state()
        self.save_config()

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        app_name = os.path.basename(self.app_path_val) if self.app_path_val else "N/A"
        self.log_status(f"Monitoring started for {app_name}. Block after {self.end_hour_val:02d}:{self.end_minute_val:02d}.")

    def on_stop_monitoring(self, event=None):
        if self.monitoring_active:
            self.monitoring_active = False
            self.stop_event.set()
            # Daemon thread, join is optional but good for cleaner exit if needed
            # if self.monitor_thread and self.monitor_thread.is_alive():
            #    self.monitor_thread.join(timeout=1)
            self.update_ui_for_monitoring_state()
            self.log_status("Monitoring stopped.")

    def monitor_loop(self):
        target_app_full_path = self.app_path_val
        if not target_app_full_path:
            self.log_status("Critical Error: Target application path missing in monitor_loop.")
            wx.CallAfter(self.on_stop_monitoring)
            return

        target_app_name = os.path.basename(target_app_full_path).lower()
        last_status_message = ""

        while not self.stop_event.is_set():
            try:
                current_time = datetime.datetime.now()
                current_date = current_time.date()
                # Ensure these are read fresh in case they are changed by some other mechanism (though not in current design)
                end_time_today = current_time.replace(hour=self.end_hour_val, minute=self.end_minute_val, second=0, microsecond=0)

                # --- Daily Reset Logic ---
                if self.block_activated_today and self.date_block_activated and current_date > self.date_block_activated:
                    self.log_status(f"New day ({current_date}). Resetting block for {target_app_name}.")
                    self.block_activated_today = False
                    self.date_block_activated = None # Reset date
                    self.save_config() # Persist reset state
                    last_status_message = "" # Force status update

                # --- Block Activation Logic ---
                if not self.block_activated_today and current_time >= end_time_today:
                    self.log_status(f"End time {end_time_today.strftime('%H:%M')} reached. Activating block for {target_app_name}.")
                    self.block_activated_today = True
                    self.date_block_activated = current_date
                    self.save_config()
                    last_status_message = ""

                # --- Process Killing Logic ---
                if self.block_activated_today:
                    current_message = f"Blocking {target_app_name}. Access denied until tomorrow."
                    if current_message != last_status_message:
                        self.log_status(current_message)
                        last_status_message = current_message

                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if proc.info['exe'] and os.path.normcase(proc.info['exe']) == os.path.normcase(target_app_full_path):
                                self.log_status(f"Found running instance of {target_app_name} (PID: {proc.pid}). Terminating...")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=1)
                                except psutil.TimeoutExpired:
                                    self.log_status(f"Force killing {target_app_name} (PID: {proc.pid}).")
                                    proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                        except Exception as e_proc:
                            self.log_status(f"Error checking/terminating '{proc.name() if proc else 'unknown'}': {e_proc}")
                else: # Not blocked yet for today
                    current_message = f"Monitoring {target_app_name}. Allowed until {end_time_today.strftime('%H:%M')}."
                    if current_message != last_status_message:
                        self.log_status(current_message)
                        last_status_message = current_message

            except Exception as e_loop:
                self.log_status(f"Error in monitoring loop: {e_loop}")
                last_status_message = ""

            self.stop_event.wait(timeout=3) # Check interval (e.g., 3 seconds)

        self.log_status("Monitoring thread has stopped.")
        wx.CallAfter(self.update_ui_for_monitoring_state)

    def toggle_visibility(self):
        if self.IsShown():
            self.Hide()
        else:
            self.Show()
            self.Raise() # Bring to front

    def on_minimize_to_tray(self, event):
        """Called when the (X) close button is pressed or app is minimized."""
        if isinstance(event, wx.CloseEvent): # From X button
            self.Hide()
            # event.Veto() # if you don't want the default close behavior, but Hide() is enough
        elif isinstance(event, wx.IconizeEvent): # From minimize button
            if event.IsIconized():
                self.Hide()
        # For CloseEvent, if you don't Veto, the frame might be destroyed.
        # Hiding is usually sufficient for "minimize to tray" behavior.
        # If event.Veto() is used, ensure Hide() is called.

    def on_iconize_to_tray(self, event):
        if event.IsIconized():
            self.Hide() # Hide the frame when it's minimized
            # self.taskBarIcon.ShowBalloon("Minimized", "App is running in the tray.") # Optional balloon

    def on_proper_exit(self, event=None, is_restarting=False):
        self.log_status("Exiting application...")
        if self.monitoring_active:
            self.on_stop_monitoring()
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.log_status("Waiting for monitor thread to finish...")
                self.monitor_thread.join(timeout=2) # Give it a moment to stop
        if not is_restarting: # Don't save config if restarting as admin, new instance will handle
            self.save_config()

        if self.taskBarIcon:
            self.taskBarIcon.cleanup() # Unbind and destroy taskbar icon
            self.taskBarIcon = None

        self.Destroy()
        # wx.GetApp().ExitMainLoop() # Also ensure main loop exits

if __name__ == '__main__':
    # Create a dummy icon.png if it doesn't exist for testing tray icon
    if not os.path.exists(TRAY_ICON_PATH):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (16, 16), color = 'blue')
            d = ImageDraw.Draw(img)
            d.text((2,2), "B", fill=(255,255,0))
            img.save(TRAY_ICON_PATH)
            print(f"Created dummy {TRAY_ICON_PATH} for testing.")
        except ImportError:
            print(f"Pillow not installed. Cannot create dummy {TRAY_ICON_PATH}. Please create it manually or app will use a stock icon.")
        except Exception as e_img:
            print(f"Error creating dummy icon: {e_img}")


    app = wx.App(False)
    frame = AppBlockerFrame(None, "App Time Blocker v2")
    # Frame is shown from within its __init__ or by user from tray
    app.MainLoop()