from __future__ import print_function
import os.path, sys, json, datetime
from datetime import datetime as dt

import googleapiclient.errors
import googleapiclient.discovery
from googleapiclient.discovery import build_from_document
from google.oauth2 import service_account

#   Script Information
#   Website = "https://www.twitch.tv/Crimdahl"
#   Description = "Submits flags in a .json file to Google Sheets."
#   Creator = "Crimdahl"
#   Version = "2"


def log(line):
    global log_file
    try:
        log_file = open(log_path, "a+")
        print(line)
        if log_file:
            log_file.writelines(str(datetime.datetime.now()) + " " + line + "\n")
        log_file.close()
    except IOError:
        pass


try:
    script_run_path = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_run_path, "Streamlabs Chatbot.exe")):
        streamlabs_script_path = os.path.join(script_run_path, "Services/Scripts/FlagTracker")
    else:
        streamlabs_script_path = script_run_path
    settings_path = os.path.join(streamlabs_script_path, "settings.json")
    redemptions_path = os.path.join(streamlabs_script_path, "redemptions.json")
    token_path = os.path.join(streamlabs_script_path, "token.json")
    log_path = os.path.join(streamlabs_script_path, "googlesheetsupdaterlog.txt")
    log_file = None

    api_path = None
    if hasattr(sys, "_MEIPASS"):
        api_path = os.path.join(sys._MEIPASS, "sheets.v4.json")
    else:
        api_path = os.path.join(os.getcwd(), "sheets.v4.json")

    if hasattr(sys, "_MEIPASS"):
        log("sys has MEIPASS")
        if os.path.isfile(os.path.join(os.getcwd(), "credentials.json")):
            credentials_path = os.path.join(os.getcwd(), "credentials.json")
        else:
            credentials_path = os.path.join(sys._MEIPASS, "credentials.json")
    else:
        log("sys does not have MEIPASS")
        credentials_path = os.path.join(os.getcwd(), "credentials.json")
except Exception as ex:
    log(str(ex))

def load_redemptions():
    if redemptions_path and os.path.isfile(redemptions_path):
        with open(redemptions_path, mode="rb") as infile:
            data = infile.read().decode("utf-8-sig")
            json_data = json.loads(data)  # Load the json data
            log("Redemptions file loaded from " + redemptions_path)
            return json_data
    else:
        raise IOError(
            "Error loading redemptions file " + redemptions_path + " Is the updater in the script directory with " +
            "the redemptions.json file? ")


def load_settings():
    if settings_path and os.path.isfile(settings_path):
        with open(settings_path, mode="rb") as infile:
            data = infile.read().decode("utf-8-sig")
            json_data = json.loads(data)
            log("Settings file loaded from " + settings_path)
            return json_data
    else:
        raise IOError(
            "Error loading settings file " + settings_path + " Is the updater in the script directory with " +
            "the settings.json file?")


def main():
    global script_run_path
    global streamlabs_script_path

    try:
        log("-------------------------------------------")
        log("Run datetime: " + dt.now().strftime("%Y-%m-%d %I:%M:%S %p"))
        print()
        if os.path.isfile(credentials_path):
            log("Application credentials loaded successfully.")
        else:
            log("ERROR: No credentials.json found packed in with the updater. Crimdahl messed up!")
            raise AttributeError("No credentials.json found packed in with the updater.")

        settings = load_settings()
        redemptions = load_redemptions()
        api_scope = ['https://www.googleapis.com/auth/spreadsheets']

        if "SpreadsheetID" in settings.keys() and not settings["SpreadsheetID"] == "":
            spreadsheet_id = settings["SpreadsheetID"]
            print("Spreadsheet ID identified as " + str(spreadsheet_id) + " from streamlabs script settings.")
        else:
            raise AttributeError(
                "No Spreadsheet ID existed in settings.json. Please add your spreadsheet's ID in the chatbot settings.")

        if "Sheet" in settings.keys() and not settings["Sheet"] == "":
            sheet_name = settings["Sheet"]
            cell_range = str(sheet_name) + "!A:D"
            print("Sheet name identified as " + str(sheet_name) + " from streamlabs script settings.")
        else:
            raise AttributeError(
                "No Sheet Name existed in settings.json. Please add your sheet's name in the chatbot settings.")

        log("Attempting to sync your Google Sheet with redemptions.json.")
        if redemptions is not None and len(redemptions) > 0:
            creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=api_scope)
            log("Getting Sheets v4 API Information.")
            api = None
            if api_path and os.path.isfile(api_path):
                with open(api_path, mode="rb") as infile:
                    data = infile.read().decode("utf-8-sig")
                    api = json.loads(data)  # Load the json data
                    log("Sheets v4 API Information loaded.")
            else:
                log("ERROR: Failed to load Sheets v4 API Information.")

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
                log("Sync successful.")
            except googleapiclient.errors.HttpError as sheets_error:
                print("An HTTP Error was returned from the Google server: " + str(sheets_error))
        else:
            log("There were no redemptions.")
    # If any unhandled exceptions occur, log them and then close the log file
    except Exception as e1:
        try:
            log("Unhandled exception: " + str(e1))
        except IOError:
            pass
    finally:
        if log_file:
            log_file.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e))
