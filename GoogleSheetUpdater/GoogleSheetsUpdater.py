import os.path
import sys
import json
import logging
from datetime import datetime as dt

import googleapiclient.errors
import googleapiclient.discovery
from googleapiclient.discovery import build_from_document
from google.oauth2 import service_account

#   Script Information
#   Website = "https://www.twitch.tv/Crimdahl"
#   Description = "Submits flags in a .json file to Google Sheets."
#   Creator = "Crimdahl"
#   Version = "2.0.2"


SCRIPT_RUN_PATH = os.path.dirname(sys.argv[0])
LOG_PATH = os.path.join(SCRIPT_RUN_PATH, "googlesheetsupdaterlog.txt")
SETTINGS_PATH = os.path.join(SCRIPT_RUN_PATH, "settings.json")
REDEMPTIONS_PATH = os.path.join(SCRIPT_RUN_PATH, "redemptions.json")

log_file = None
api_path = None
if hasattr(sys, "_MEIPASS"):
    api_path = os.path.join(sys._MEIPASS, "sheets.v4.json")
else:
    api_path = os.path.join(os.getcwd(), "sheets.v4.json")

if hasattr(sys, "_MEIPASS"):
    if os.path.isfile(os.path.join(os.getcwd(), "credentials.json")):
        credentials_path = os.path.join(os.getcwd(), "credentials.json")
    else:
        credentials_path = os.path.join(sys._MEIPASS, "credentials.json")
else:
    credentials_path = os.path.join(os.getcwd(), "credentials.json")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(funcName)s |  %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)


def load_redemptions():
    if REDEMPTIONS_PATH and os.path.isfile(REDEMPTIONS_PATH):
        try:
            with open(REDEMPTIONS_PATH, mode="rb") as infile:
                data = infile.read().decode("utf-8-sig")
                json_data = json.loads(data)  # Load the json data
                logging.debug("Redemptions file loaded from " + REDEMPTIONS_PATH)
                return json_data
        except ValueError as ex:
            logging.error("Error loading redemptions file. Is it empty? " + str(ex))
            return {}
    else:
        raise IOError(
            "Error loading redemptions file " + REDEMPTIONS_PATH + " Is the updater in the script directory with " +
            "the redemptions.json file? ")


def load_settings():
    if SETTINGS_PATH and os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, mode="rb") as infile:
            data = infile.read().decode("utf-8-sig")
            json_data = json.loads(data)
            return json_data
    else:
        raise IOError(
            "Error loading settings file " + SETTINGS_PATH + " Is the updater in the script directory with " +
            "the settings.json file?")


def main():
    global SCRIPT_RUN_PATH, LOG_PATH

    try:
        if os.path.isfile(credentials_path):
            logging.debug("Application credentials loaded successfully.")
        else:
            logging.critical("ERROR: No credentials.json found packed in with the updater. Crimdahl messed up!")
            raise AttributeError("No credentials.json found packed in with the updater.")

        settings = load_settings()
        logging.debug("Settings file loaded from " + SETTINGS_PATH)
        redemptions = load_redemptions()
        api_scope = ['https://www.googleapis.com/auth/spreadsheets']

        if "SpreadsheetID" in settings.keys() and not settings["SpreadsheetID"] == "":
            spreadsheet_id = settings["SpreadsheetID"]
            logging.debug("Spreadsheet ID identified as " + str(spreadsheet_id) + " from streamlabs script settings.")
        else:
            raise AttributeError(
                "No Spreadsheet ID existed in settings.json. Please add your spreadsheet's ID in the chatbot settings.")

        if "Sheet" in settings.keys() and not settings["Sheet"] == "":
            sheet_name = settings["Sheet"]
            cell_range = str(sheet_name) + "!A:D"
            logging.debug("Sheet name identified as " + str(sheet_name) + " from streamlabs script settings.")
        else:
            raise AttributeError(
                "No Sheet Name existed in settings.json. Please add your sheet's name in the chatbot settings.")

        logging.debug("Attempting to sync Google Sheet with redemptions.json.")
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=api_scope)
        logging.debug("Getting Sheets v4 API Information.")
        api = None
        if api_path and os.path.isfile(api_path):
            with open(api_path, mode="rb") as infile:
                data = infile.read().decode("utf-8-sig")
                api = json.loads(data)  # Load the json data
                logging.debug("Sheets v4 API Information loaded.")
        else:
            logging.critical("ERROR: Failed to load Sheets v4 API Information.")

        service = build_from_document(api, credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        values = [["", "", "", "Sheet Last Synced on " + dt.now().strftime("%Y-%m-%d %I:%M:%S %p")],
                  ["# in Queue", "Username", "Game", "Message"],
                  ["----------", "----------", "----------", "----------"]]
        index = 1

        for redemption in redemptions:
            values.append([str(index), redemption["Username"], redemption["Game"], redemption["Message"]])
            index = index + 1
        for i in range(50):
            values.append(["", "", "", ""])

        body = {"values": values}

        try:
            sheet.values().update(spreadsheetId=spreadsheet_id, range=cell_range,
                                  valueInputOption="USER_ENTERED", body=body).execute()
            logging.debug("Sync successful.")
        except googleapiclient.errors.HttpError as sheets_error:
            logging.error("An HTTP Error was returned from the Google server: " + str(sheets_error))

        if "AllowGistUpload" in settings and settings["AllowGistUpload"]:
            import requests
            with open(LOG_PATH) as logging_file:
                contents = logging_file.read()
                requests.post(
                    url="https://api.github.com/gists",
                    headers={
                        "accept": "application/vnd.github+json",
                        "authorization": "Bearer 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"
                    },
                    json={
                        "description": "GoogleSheetsUpdater Log File",
                        "files": {
                            os.path.basename(LOG_PATH): {
                                "content": contents
                            }
                        },
                        "public": True
                    }
                )
        if "RetainLogFiles" in settings and not settings["RetainLogFiles"]:
            for handler in logging.getLogger().handlers:
                handler.close()
                logging.getLogger().removeHandler(handler)
            os.remove(LOG_PATH)

    # If any unhandled exceptions occur, log them and then close the log file
    except Exception as e1:
        try:
            logging.error("Unhandled exception: " + str(e1))
        except IOError:
            pass


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e))
