import unittest
from unittest import mock
import json
import os
import sys
import datetime

# Adjust sys.path to ensure 'app_blocker' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app_blocker import config

# Store original values to restore them later
ORIGINAL_APP_DATA_DIR = config.APP_DATA_DIR
ORIGINAL_CONFIG_FILE_PATH = config.CONFIG_FILE_PATH

class TestConfigManager(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test configuration files
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_app_data"))
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        # Mock the config module's constants to use a temporary test path
        config.APP_DATA_DIR = self.test_dir
        config.CONFIG_FILE_PATH = os.path.join(self.test_dir, "test_config.json")

        # Clean up any existing test config file before each test
        if os.path.exists(config.CONFIG_FILE_PATH):
            os.remove(config.CONFIG_FILE_PATH)

    def tearDown(self):
        # Clean up the test config file and directory
        if os.path.exists(config.CONFIG_FILE_PATH):
            os.remove(config.CONFIG_FILE_PATH)
        if os.path.exists(self.test_dir):
            # Check if directory is empty before removing
            if not os.listdir(self.test_dir):
                 os.rmdir(self.test_dir)
            else: # If other files were created unexpectedly, clean them up.
                 for f in os.listdir(self.test_dir):
                     os.remove(os.path.join(self.test_dir, f))
                 os.rmdir(self.test_dir)


        # Restore original config paths
        config.APP_DATA_DIR = ORIGINAL_APP_DATA_DIR
        config.CONFIG_FILE_PATH = ORIGINAL_CONFIG_FILE_PATH


    @mock.patch('os.path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        
        loaded = config.load_config_from_file()
        
        self.assertEqual(loaded["app_path"], config.DEFAULT_APP_PATH)
        self.assertEqual(loaded["end_hour"], config.DEFAULT_END_HOUR)
        self.assertEqual(loaded["end_minute"], config.DEFAULT_END_MINUTE)
        self.assertEqual(loaded["block_activated_today"], config.DEFAULT_BLOCK_ACTIVATED_TODAY)
        self.assertIsNone(loaded["date_block_activated"])
        mock_exists.assert_called_once_with(config.CONFIG_FILE_PATH)

    @mock.patch('builtins.print') # To capture log messages printed to console
    @mock.patch('builtins.open', new_callable=mock.mock_open, read_data="this is not json")
    @mock.patch('os.path.exists')
    def test_load_config_invalid_json(self, mock_exists, mock_file_open, mock_print):
        mock_exists.return_value = True
        
        loaded = config.load_config_from_file()
        
        self.assertEqual(loaded["app_path"], config.DEFAULT_APP_PATH)
        self.assertEqual(loaded["end_hour"], config.DEFAULT_END_HOUR)
        self.assertEqual(loaded["end_minute"], config.DEFAULT_END_MINUTE)
        self.assertEqual(loaded["block_activated_today"], config.DEFAULT_BLOCK_ACTIVATED_TODAY)
        self.assertIsNone(loaded["date_block_activated"])
        
        mock_exists.assert_called_once_with(config.CONFIG_FILE_PATH)
        mock_file_open.assert_called_once_with(config.CONFIG_FILE_PATH, "r")
        mock_print.assert_any_call(f"Error loading config from {config.CONFIG_FILE_PATH}: Expecting value: line 1 column 1 (char 0). Using defaults.")


    def test_load_config_successful_today_not_blocked(self):
        sample_config_data = {
            "app_path": "/path/to/app.exe",
            "end_hour": 20,
            "end_minute": 30,
            "block_activated_today": False,
            "date_block_activated": None 
        }
        with open(config.CONFIG_FILE_PATH, 'w') as f:
            json.dump(sample_config_data, f)

        loaded = config.load_config_from_file()
        
        self.assertEqual(loaded["app_path"], sample_config_data["app_path"])
        self.assertEqual(loaded["end_hour"], sample_config_data["end_hour"])
        self.assertEqual(loaded["end_minute"], sample_config_data["end_minute"])
        self.assertEqual(loaded["block_activated_today"], False) # Should remain False
        self.assertIsNone(loaded["date_block_activated"])


    @mock.patch('app_blocker.config.datetime') # Mock datetime within the config module
    def test_load_config_block_activated_yesterday_resets(self, mock_datetime):
        today = datetime.date(2024, 5, 22)
        yesterday = today - datetime.timedelta(days=1)
        
        mock_datetime.date.today.return_value = today
        # This is needed because strptime is part of datetime.datetime, not datetime.date
        mock_datetime.datetime.strptime = datetime.datetime.strptime 

        sample_config_data = {
            "app_path": "/path/to/app.exe",
            "end_hour": 17,
            "end_minute": 0,
            "block_activated_today": True,
            "date_block_activated": yesterday.isoformat() 
        }
        with open(config.CONFIG_FILE_PATH, 'w') as f:
            json.dump(sample_config_data, f)
            
        loaded = config.load_config_from_file()
        
        self.assertEqual(loaded["app_path"], sample_config_data["app_path"])
        self.assertEqual(loaded["block_activated_today"], False) # Should reset
        self.assertIsNone(loaded["date_block_activated"])      # Should reset


    @mock.patch('app_blocker.config.datetime') # Mock datetime within the config module
    def test_load_config_block_activated_today_persists(self, mock_datetime):
        today = datetime.date(2024, 5, 22)
        
        mock_datetime.date.today.return_value = today
        mock_datetime.datetime.strptime = datetime.datetime.strptime

        sample_config_data = {
            "app_path": "/path/to/app.exe",
            "end_hour": 17,
            "end_minute": 0,
            "block_activated_today": True,
            "date_block_activated": today.isoformat()
        }
        with open(config.CONFIG_FILE_PATH, 'w') as f:
            json.dump(sample_config_data, f)

        loaded = config.load_config_from_file()

        self.assertEqual(loaded["app_path"], sample_config_data["app_path"])
        self.assertEqual(loaded["block_activated_today"], True) # Should persist
        self.assertEqual(loaded["date_block_activated"], today) # Should persist


    @mock.patch('builtins.print')
    @mock.patch('json.dump')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('os.makedirs') # To check if it's called when APP_DATA_DIR might not exist
    @mock.patch('os.path.exists') # To simulate APP_DATA_DIR not existing initially
    def test_save_config_creates_dir_and_saves(self, mock_path_exists, mock_makedirs, mock_open_file, mock_json_dump, mock_print):
        # Simulate APP_DATA_DIR does not exist for the first check in config.py,
        # but then exists for the CONFIG_FILE_PATH check within save_config_to_file (if we were testing that part).
        # For this test, we are mainly concerned with os.makedirs for APP_DATA_DIR if it's part of save.
        # However, APP_DATA_DIR creation is at module load in config.py.
        # So, we'll test if save_config_to_file correctly calls open and json.dump.
        
        # Let's assume APP_DATA_DIR (self.test_dir) is already created by setUp.
        # We want to ensure save_config_to_file writes to config.CONFIG_FILE_PATH.
        mock_path_exists.return_value = True # Assume directory exists for simplicity of this save test

        app_path = "/test/app.exe"
        end_hour = 10
        end_minute = 5
        block_activated = True
        date_activated = datetime.date(2024, 1, 1)

        config.save_config_to_file(app_path, end_hour, end_minute, block_activated, date_activated)

        # Check if open was called correctly
        mock_open_file.assert_called_once_with(config.CONFIG_FILE_PATH, "w")
        
        # Check if json.dump was called with the correct data
        expected_data = {
            "app_path": app_path,
            "end_hour": end_hour,
            "end_minute": end_minute,
            "block_activated_today": block_activated,
            "date_block_activated": date_activated.isoformat()
        }
        mock_json_dump.assert_called_once_with(expected_data, mock_open_file(), indent=4)
        # The print statement in config.py was commented out, so we don't check for it.
        # If it were active, the check would be:
        # mock_print.assert_any_call(f"Configuration saved to {config.CONFIG_FILE_PATH}")


    @mock.patch('builtins.print')
    def test_load_config_malformed_date_string(self, mock_print):
        sample_config_data = {
            "app_path": "/path/to/app.exe",
            "end_hour": 17,
            "end_minute": 0,
            "block_activated_today": True,
            "date_block_activated": "this-is-not-a-date" 
        }
        with open(config.CONFIG_FILE_PATH, 'w') as f:
            json.dump(sample_config_data, f)
            
        loaded = config.load_config_from_file()
        
        self.assertEqual(loaded["app_path"], sample_config_data["app_path"])
        self.assertEqual(loaded["block_activated_today"], False) # Should reset due to malformed date
        self.assertIsNone(loaded["date_block_activated"])      # Should reset


if __name__ == '__main__':
    unittest.main()
