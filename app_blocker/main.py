import wx
import os # For os.path.exists
import gettext

# Assuming main.py is in app_blocker, and locale is at the project root.
locale_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'locale'))
if not os.path.isdir(locale_dir):
    alt_locale_dir = os.path.abspath(os.path.join(os.getcwd(), 'locale'))
    if os.path.isdir(alt_locale_dir):
        locale_dir = alt_locale_dir
    else:
        print(f"Locale directory not found at {locale_dir} or {alt_locale_dir}. Using fallback gettext.")
        locale_dir = None

if locale_dir and os.path.isdir(locale_dir):
    translation = gettext.translation('messages', localedir=locale_dir, languages=['en'], fallback=True)
    _ = translation.gettext
else:
    _ = gettext.gettext


# Import the main frame from the gui module
from .gui import AppBlockerFrame
# Import TRAY_ICON_PATH for the dummy icon creation (config might be better place for TRAY_ICON_PATH itself)
from .config import TRAY_ICON_PATH 


APP_NAME = _("App Time Blocker v2") # For window title - updated from "App Time Blocker v2"
TRAY_TOOLTIP_TEXT = _('App Time Blocker Tray') # For taskbar icon tooltip

if __name__ == '__main__':
    # Create a dummy icon.png if it doesn't exist for testing tray icon
    # This logic might be moved to gui.py later or a utility module
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
    # Pass the translated title and tooltip text to the frame
    frame = AppBlockerFrame(None, title=APP_NAME, tray_tooltip_text=TRAY_TOOLTIP_TEXT) 
    app.MainLoop()
