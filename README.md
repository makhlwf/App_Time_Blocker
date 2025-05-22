# App Time Blocker

## Project Description
App Time Blocker is a Windows application designed to help users manage their time by blocking specified programs after a user-defined time limit each day. Once the set time is reached, the chosen application will be blocked for the remainder of the day, with the block automatically resetting the next day.

## Features
*   **Application Selection:** Allows users to select any executable application (`.exe`) for monitoring and blocking.
*   **Customizable Block Time:** Users can define a specific time (in HH:MM format) after which the application's usage will be restricted.
*   **Daily Reset:** The block is enforced for the rest of the day and automatically resets on the following day.
*   **Background Monitoring:** The application monitors the target program in the background without constant user interaction.
*   **System Tray Integration:**
    *   Includes a system tray icon for easy access.
    *   Options to show/hide the main application window.
    *   Option to exit the application directly from the tray menu.
*   **Configuration Persistence:** User settings (selected application path, block time, language preference) are saved locally and reloaded when the application starts.
*   **Administrator Privileges:**
    *   Checks if it's running with administrator privileges, which are often required to terminate other applications effectively.
    *   Prompts the user to restart as administrator if necessary.
*   **Modular Codebase:** The source code is organized into modules for configuration, core blocking logic, and GUI, facilitating easier maintenance and future development.
*   **Internationalization (i18n):** Supports multiple languages through `gettext`. 
*   **Language Selection:** Choose between available languages (currently English and Arabic [placeholder translations]). A restart is required for changes to take full effect.

## How to Run / Installation

### Prerequisites
*   **Python:** Python 3.x (developed with 3.10+)
*   **wxPython:** A cross-platform GUI toolkit for Python.
    *   Installation: `pip install wxpython`
*   **psutil:** A cross-platform library for retrieving information on running processes and system utilization.
    *   Installation: `pip install psutil`
*   **Pillow (Optional):** Python Imaging Library, used in this project to create a dummy tray icon if `icon.png` is missing.
    *   Installation: `pip install Pillow`
*   **gettext (for developers adding translations):** GNU gettext utilities are needed to work with `.po` and `.mo` files (e.g., `msgfmt`, `pygettext3`).

### Running the Application
1.  Ensure all prerequisites are installed.
2.  The main entry point for the application is `app_blocker/main.py`.
3.  To run the application, navigate to the project's root directory in your terminal and execute:
    ```bash
    python -m app_blocker.main
    ```
    (Use `python3` instead of `python` if that's how your system is configured).
4.  **Tray Icon:**
    *   For the best experience, place a 16x16 or 32x32 `icon.png` file in the root directory of the project. This icon will be used for the system tray.
    *   If `icon.png` is not found and Pillow is installed, a simple dummy icon will be generated at runtime.

## Configuration
The application's main window provides the following controls:

*   **Application to Block:**
    *   A read-only text field displaying the path to the selected application.
    *   **"Browse..." button:** Opens a file dialog to select the `.exe` file of the application you wish to block.
*   **Block After (HH:MM):**
    *   Two spin controls to set the hour (0-23) and minute (0-59) after which the selected application will be blocked.
*   **Controls:**
    *   **"Start Monitoring" button:** Begins monitoring the selected application. Settings are saved when monitoring starts.
    *   **"Stop Monitoring" button:** Stops the current monitoring process.
*   **Language Menu:**
    *   Located in the menu bar (Language > Select Language).
    *   Allows switching between English and Arabic.
    *   The application saves this preference and must be restarted for the language change to fully apply to all UI elements.
*   **Status Log:**
    *   A text area that displays real-time status messages, such as when monitoring starts/stops, when an application is blocked, or any errors that occur.

### Configuration File
*   The application settings are stored in a JSON file located in the user's local application data directory.
*   Path: `%APPDATA%\Local\AppBlockerWxV2\app_blocker_config_wx_v2.json`
    *   This typically translates to `C:\Users\<YourUsername>\AppData\Local\AppBlockerWxV2\app_blocker_config_wx_v2.json` on Windows.
    *   The directory and file are created automatically if they don't exist.
*   This file stores the selected application path, block time, daily block status, and chosen language.

## Code Structure
The application is organized within the `app_blocker` package:

*   `app_blocker/`
    *   `__init__.py`: Makes `app_blocker` a Python package.
    *   `main.py`: The main entry point of the application. It initializes the `wx.App` and the main application frame (`AppBlockerFrame`). It also handles the initial `gettext` setup based on the configured language.
    *   `gui.py`: Contains all wxPython UI classes, including `AppBlockerFrame` (the main window) and `AppTaskBarIcon` (the system tray icon). It manages UI layout, event handling, language selection menu, and interactions with the other modules. Internationalization for UI strings is primarily handled here.
    *   `blocker.py`: Implements the core logic for monitoring the target application's process and terminating it when the block condition is met. It uses `psutil` for process iteration and `threading` to run the monitoring loop in the background.
    *   `config.py`: Manages loading and saving the application's configuration (target application path, block time, daily block status, language) to a JSON file. It also defines constants related to configuration paths and default values.

## Translations (Internationalization - i18n)
The application uses the `gettext` module for internationalization, allowing UI strings to be translated into multiple languages.

*   **Current Languages:**
    *   English (`en`) - Default
    *   Arabic (`ar`) - Placeholder translations
*   **Translation Files Location:** `locale/` directory in the project root.
    *   `locale/messages.pot`: This is the template file generated by `pygettext3`. It contains all strings extracted from the source code that are marked for translation.
    *   `locale/<lang_code>/LC_MESSAGES/messages.po`: These are human-readable plain text files for each supported language (e.g., `locale/en/LC_MESSAGES/messages.po` for English). Translators edit these files to provide translations for each `msgid`.
    *   `locale/<lang_code>/LC_MESSAGES/messages.mo`: These are compiled, machine-readable binary files generated from the `.po` files. The application uses these `.mo` files at runtime to load translations.

### Adding a New Language (Basic Guide)
1.  **Create Language Directory:**
    ```bash
    mkdir -p locale/<lang_code>/LC_MESSAGES/
    ```
    Replace `<lang_code>` with the appropriate ISO 639-1 language code (e.g., `fr` for French, `es` for Spanish).
2.  **Create `.po` File:** Copy the template file to your new language directory:
    ```bash
    cp locale/messages.pot locale/<lang_code>/LC_MESSAGES/messages.po
    ```
3.  **Translate Strings:** Edit the new `locale/<lang_code>/LC_MESSAGES/messages.po` file:
    *   For each `msgid "Original string"`, fill in the `msgstr "Translated string"` with the translation.
    *   Update the header fields in the `.po` file (e.g., `Language: <lang_code>`, `Last-Translator`, `Language-Team`, `Plural-Forms`).
4.  **Compile `.mo` File:** Use `msgfmt` (part of the `gettext` tools) to compile your `.po` file into a `.mo` file:
    ```bash
    msgfmt -o locale/<lang_code>/LC_MESSAGES/messages.mo locale/<lang_code>/LC_MESSAGES/messages.po
    ```
    Ensure `gettext` tools are installed on your system (on Debian/Ubuntu: `sudo apt-get install gettext`).
5.  **Application Integration:**
    *   Add the new language option to the "Language" menu in `app_blocker/gui.py` (`AppBlockerFrame.InitUI`).
    *   Update the `on_select_language` handler in `app_blocker/gui.py` to recognize the new language code.
    *   The application's `gettext` setup in `app_blocker/main.py` and `app_blocker/gui.py` should automatically pick up the new language if the `.mo` file is correctly placed and the language code is used.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

To help streamline the process, we have provided templates for issues and pull requests:

*   **Issue Templates:** When creating an issue, please use one of the available templates (Bug Report, Feature Request) to provide detailed and structured information. These can be found when you click "New Issue" on GitHub, and the template files are located in the `.github/ISSUE_TEMPLATE` directory of this repository.
*   **Pull Request Template:** When submitting a pull request, GitHub will automatically populate the PR description with the template from `.github/PULL_REQUEST_TEMPLATE.md`. Please fill this out to describe your changes, related issues, and testing performed.

New translations are also a very welcome form of contribution. Please follow the guide under "Adding a New Language" and submit a pull request with your changes.

## License
This project is licensed under the **MIT License**. See the `LICENSE` file for details.
