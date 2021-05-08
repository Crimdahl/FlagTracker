from __future__ import print_function
import os.path, sys, codecs, json, datetime
from googleapiclient.discovery import build_from_document
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

chatbot_path = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(chatbot_path, "Services\Scripts\FlagTracker")
settings_path = os.path.join(script_path, "settings.json")
redemptions_path = os.path.join(script_path, "redemptions.json")
token_path = os.path.join(script_path, "token.json")
#credentials_path = os.path.join(script_path, "credentials.json")
log_path = os.path.join(script_path, "googlesheetsupdaterlog.txt")
#log_file = None

API_path = None
if hasattr(sys, "_MEIPASS"):
    API_path = os.path.join(sys._MEIPASS, "sheets.v4.json")
else:
    API_path = os.path.join(script_path, "sheets.v4.json")

if hasattr(sys, "_MEIPASS"):
    credentials_path = os.path.join(sys._MEIPASS, "credentials.json")
else:
    credentials_path = os.path.join(script_path, "credentials.json")

def loadRedemptions():
    log("Attempting to load redemptions file.")
    if redemptions_path and os.path.isfile(redemptions_path):
        with open(redemptions_path, encoding="utf-8-sig", mode="r") as infile:
            return json.load(infile)    #Load the json data
            log("Redemptions file loaded.")
    else:
        log("Error loading redemptions file at " + redemptions_path)

def loadSettings():
    log("Attempting to load settings file.")
    if settings_path and os.path.isfile(settings_path):
        with codecs.open(settings_path, encoding="utf-8-sig", mode="r") as f:
            return json.load(f)
            log("Settings file loaded.")
    else:
        log("Error loading settings file at " + settings_path)

def main():
    global chatbot_path
    global script_path
    global log_file
    log_file = open(log_path, "a+")
    try:
        log_file.write("\n\n")
        log("Chatbot path: " + chatbot_path)
        log("Script path: " + script_path)
        log("Settings path: " + settings_path)
        log("Redemptions path: " + redemptions_path)
        log("API path: " + API_path)
        log("Token path: " + token_path)
        log("Credentials path: " + credentials_path)
        if(os.path.isfile(credentials_path)):
            log("Credentials found.")
        else:
            log("ERROR: No credentials.json found packed in with the updater.")
            raise AttributeError("No credentials.json found packed in with the updater.")

        settings = {}
        redemptions = {}
        settings = loadSettings()
        redemptions = loadRedemptions()
        spreadsheet_id = ""
        cell_range = ""
        api_scope = ['https://www.googleapis.com/auth/spreadsheets']

        log("Script Path is " + script_path)
        log("Getting Spreadsheet ID from " + settings_path)
        if "SpreadsheetID" in settings.keys():
            spreadsheet_id = settings["SpreadsheetID"]
        else:
            log("No SpreadsheetID existed in config.json. Please add your spreadsheet's ID in the chatbot settings.")
            raise AttributeError("No spreadsheet ID existed in the settings file.")
        log("Spreadsheet ID is " + spreadsheet_id)

        log("Getting Sheet Name.")
        if "Sheet" in settings:
            cell_range = str(settings["Sheet"]) + "!A:C"
        else:
            log("No Sheet Name existed in config.json. Please add your sheet's name in the chatbot settings.")
            raise AttributeError("No Sheet Name existed in the settings file.")
        log("Sheet Name and cell range is " + cell_range)

        log("Attempting to sync redemptions.json with your Google Sheet.")
        if redemptions is not None and  len(redemptions) > 0:
            creds = None
            # The file token.json stores the user's access and refresh tokens, and is
            # created automatically when the authorization flow completes for the first
            # time.
            if os.path.exists(token_path):
                log("Token file found.")
                creds = Credentials.from_authorized_user_file(token_path, api_scope)
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    log("The credentials existed, but needed a refresh. Opening browser window to authenticate.")
                    creds.refresh(Request())
                else:
                    log("The credentials did not exist or weren't valid. Opening browser window to authenticate.")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, api_scope)
                    creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                log("Authentication successful. Saving the credentials to file.")
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            log("Getting Sheets v4 API Information.")
            API = None
            if API_path and os.path.isfile(API_path):
                with open(API_path, encoding="utf-8-sig", mode="r") as infile:
                    API = json.load(infile)    #Load the json data
                    log("Sheets v4 API Information loaded.")
            else:
                log("ERROR: Failed to load Sheets v4 API Information.")
                
            service = build_from_document(API, credentials=creds)

            # Call the Sheets API
            log("Sending request to Google Sheets API.")
            sheet = service.spreadsheets()
            values = [["Username", "Game", "Message"]]
            for redemption in redemptions:
                values.append([redemption["Username"], redemption["Game"], redemption["Message"]])
            for i in range(5):
                values.append(["", "", ""])
            log("Redemption contents: " + str(values))
            body = {"values":values}
            sheet.values().update(spreadsheetId=spreadsheet_id, range=cell_range,
                                valueInputOption="USER_ENTERED", body=body).execute()
            log("Success?")
        else:
            log("There were no redemptions.")
    finally:
        log_file.close()

def log(line):
    global log_file

    log_file.writelines(str(datetime.datetime.now()) + " " + line + "\n")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e.message))
        
    