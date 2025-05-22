import os
import json
import datetime

CONFIG_FILE_NAME = "app_blocker_config_wx_v2.json"
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "AppBlockerWxV2")
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)
CONFIG_FILE_PATH = os.path.join(APP_DATA_DIR, CONFIG_FILE_NAME)

# Default values
DEFAULT_APP_PATH = ""
DEFAULT_END_HOUR = 17
DEFAULT_END_MINUTE = 0
DEFAULT_BLOCK_ACTIVATED_TODAY = False
DEFAULT_DATE_BLOCK_ACTIVATED = None

def load_config_from_file():
    """Loads configuration from the JSON file."""
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r") as f:
                config_data = json.load(f)
                
                app_path = config_data.get("app_path", DEFAULT_APP_PATH)
                end_hour = int(config_data.get("end_hour", DEFAULT_END_HOUR))
                end_minute = int(config_data.get("end_minute", DEFAULT_END_MINUTE))
                
                # Date validation and reset logic
                block_activated_today = config_data.get("block_activated_today", DEFAULT_BLOCK_ACTIVATED_TODAY)
                date_str = config_data.get("date_block_activated", None)
                date_block_activated = DEFAULT_DATE_BLOCK_ACTIVATED

                if block_activated_today and date_str:
                    try:
                        saved_block_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                        if saved_block_date == datetime.date.today():
                            date_block_activated = saved_block_date
                        elif saved_block_date < datetime.date.today():
                            # Past date, so reset block_activated_today
                            block_activated_today = False
                        # else: future date, or malformed, treat as not blocked for today (keep defaults)
                    except ValueError:
                        block_activated_today = False # Malformed date string
                else:
                    # If not block_activated_today or no date_str, ensure it's reset
                    block_activated_today = False
                
                return {
                    "app_path": app_path,
                    "end_hour": end_hour,
                    "end_minute": end_minute,
                    "block_activated_today": block_activated_today,
                    "date_block_activated": date_block_activated
                }
    except (IOError, ValueError, json.JSONDecodeError) as e:
        # Log this error appropriately in the main app, e.g., self.log_status(f"Error loading config: {e}")
        print(f"Error loading config from {CONFIG_FILE_PATH}: {e}. Using defaults.")
    
    # Return defaults if file doesn't exist or an error occurred
    return {
        "app_path": DEFAULT_APP_PATH,
        "end_hour": DEFAULT_END_HOUR,
        "end_minute": DEFAULT_END_MINUTE,
        "block_activated_today": DEFAULT_BLOCK_ACTIVATED_TODAY,
        "date_block_activated": DEFAULT_DATE_BLOCK_ACTIVATED
    }

def save_config_to_file(app_path, end_hour, end_minute, block_activated_today, date_block_activated):
    """Saves configuration to the JSON file."""
    config_to_save = {
        "app_path": app_path,
        "end_hour": end_hour,
        "end_minute": end_minute,
        "block_activated_today": block_activated_today,
        "date_block_activated": date_block_activated.isoformat() if date_block_activated else None
    }
    try:
        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(config_to_save, f, indent=4)
        # Log this success in the main app, e.g., self.log_status("Configuration saved.")
        # print(f"Configuration saved to {CONFIG_FILE_PATH}") # For CLI debugging if needed
    except IOError as e:
        # Log this error in the main app, e.g., self.log_status(f"Error saving config: {e}")
        print(f"Error saving config to {CONFIG_FILE_PATH}: {e}")

TRAY_TOOLTIP = 'App Time Blocker' # This is UI related, but often configured globally
TRAY_ICON_PATH = "icon.png"      # Same as above
