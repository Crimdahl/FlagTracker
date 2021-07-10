from __future__ import print_function
import os.path, sys, codecs, json, datetime
from googleapiclient.discovery import build_from_document
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

script_run_path = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_run_path, "Streamlabs Chatbot.exe")):
    streamlabs_script_path = os.path.join(script_run_path, "Services\Scripts\FlagTracker")
else:
    streamlabs_script_path = script_run_path
settings_path = os.path.join(streamlabs_script_path, "settings.json")
redemptions_path = os.path.join(streamlabs_script_path, "redemptions.json")
token_path = os.path.join(streamlabs_script_path, "token.json")
log_path = os.path.join(streamlabs_script_path, "googlesheetsupdaterlog.txt")
log_file = None

API_path = None
if hasattr(sys, "_MEIPASS"):
    API_path = os.path.join(sys._MEIPASS, "sheets.v4.json")
else:
    API_path = "sheets.v4.json"
    #API_path = os.path.join(streamlabs_script_path, "sheets.v4.json")

if hasattr(sys, "_MEIPASS"):
    credentials_path = os.path.join(sys._MEIPASS, "credentials.json")
else:
    credentials_path = "credentials.json"
    #credentials_path = os.path.join(streamlabs_script_path, "credentials.json")

def loadRedemptions():
    log("Attempting to load redemptions file.")
    if redemptions_path and os.path.isfile(redemptions_path):
        with open(redemptions_path, encoding="utf-8-sig", mode="r") as infile:
            log("Redemptions file loaded.")
            return json.load(infile)    #Load the json data
    else:
        raise IOError("Error loading redemptions file " + redemptions_path + " Is the updater in the script directory with the redemptions.json file? " + str(e))

def loadSettings():
    log("Attempting to load settings file.")
    if settings_path and os.path.isfile(settings_path):
        with codecs.open(settings_path, encoding="utf-8-sig", mode="r") as f:
            log("Settings file loaded.")
            return json.load(f)
    else:
        raise IOError("Error loading settings file " + settings_path + " Is the updater in the script directory with the settings.json file?")

def main():
    global script_run_path
    global streamlabs_script_path
    
    try:            
        log("\n\n")
        log("Script path: " + script_run_path)
        log("Streamlabs Script path: " + streamlabs_script_path)
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

        log("Script Path is " + streamlabs_script_path)
        log("Getting Spreadsheet ID from " + settings_path)
        if "SpreadsheetID" in settings.keys():
            spreadsheet_id = settings["SpreadsheetID"]
        else:
            raise AttributeError("No Spreadsheet ID existed in settings.json. Please add your spreadsheet's ID in the chatbot settings.")
        log("Spreadsheet ID is " + spreadsheet_id)

        log("Getting Sheet Name.")
        if "Sheet" in settings:
            cell_range = str(settings["Sheet"]) + "!A:C"
        else:
            raise AttributeError("No Sheet Name existed in settings.json. Please add your sheet's name in the chatbot settings.")
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
                    log("The credentials existed, but needed a refresh.")
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        log("Exception caught when refreshing request: " + str(e))
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
        if log_file: log_file.close()

def log(line):
    global log_file
    try:
        log_file = open(log_path, "a+")
        print(line)
        if log_file: log_file.writelines(str(datetime.datetime.now()) + " " + line + "\n")
        log_file.close()
    except Exception as e:
        pass

if __name__ == '__main__':
    try:
        main()
        #input("Success? Press any key to exit.")
    except Exception as e:
        print(str(e))
        #input("Press any key to exit.")
        
    