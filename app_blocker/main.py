import wx
import os 
import sys # Added for sys.frozen and sys._MEIPASS
import gettext

# Import configuration loading functions and constants
from .config import load_config_from_file, TRAY_ICON_PATH, DEFAULT_LANGUAGE

def get_bundle_dir():
    """ Returns the base directory for PyInstaller bundle or script directory for normal execution. """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running in a normal Python environment
        # Assumes main.py is in app_blocker, and project root is one level up.
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

MAIN_LOCALE_DIR = os.path.join(get_bundle_dir(), 'locale')

# --- Initial Language Setup ---
# Load language from config first to set up gettext correctly
app_config_values = load_config_from_file()
current_language = app_config_values.get('language', DEFAULT_LANGUAGE)

# Initialize gettext with the loaded language
try:
    if os.path.isdir(MAIN_LOCALE_DIR):
        translation = gettext.translation('messages', localedir=MAIN_LOCALE_DIR, languages=[current_language], fallback=True)
        _ = translation.gettext
    else: # Fallback if locale directory isn't found
        print(f"Locale directory not found at {MAIN_LOCALE_DIR}. Using fallback gettext.")
        _ = gettext.gettext
except Exception as e_gettext:
    print(f"Error setting up gettext in main.py with language '{current_language}': {e_gettext}. Using fallback gettext.")
    _ = gettext.gettext # Fallback

# Now import GUI components which might use _ in their definitions or need the language
from .gui import AppBlockerFrame


# Define translatable strings used in main.py
APP_NAME = _("App Time Blocker v2")
TRAY_TOOLTIP_TEXT = _('App Time Blocker Tray')

if __name__ == '__main__':
    # Create a dummy icon.png if it doesn't exist for testing tray icon
    if not os.path.exists(TRAY_ICON_PATH): # TRAY_ICON_PATH is imported from config
        try:
            from PIL import Image, ImageDraw # Pillow is an external dependency
            img = Image.new('RGB', (16, 16), color = 'blue')
            d = ImageDraw.Draw(img)
            d.text((2,2), "B", fill=(255,255,0))
            img.save(TRAY_ICON_PATH)
            print(f"Created dummy {TRAY_ICON_PATH} for testing.")
        except ImportError:
            print(f"Pillow (PIL) not installed. Cannot create dummy {TRAY_ICON_PATH}. Please create it manually or app will use a stock icon.")
        except Exception as e_img:
            print(f"Error creating dummy icon: {e_img}")

    app = wx.App(False)
    # Pass the translated title, tooltip text, and current_language to the frame
    frame = AppBlockerFrame(
        None, 
        title=APP_NAME, 
        tray_tooltip_text=TRAY_TOOLTIP_TEXT,
        current_lang=current_language # Pass loaded language
    ) 
    app.MainLoop()
