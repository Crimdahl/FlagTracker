from __future__ import print_function
import os.path, sys, codecs, json
from googleapiclient.discovery import build_from_document
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

ChatbotPath = os.path.dirname(os.path.abspath(__file__))
ScriptPath = os.path.join(ChatbotPath, "Services\Scripts\FlagTracker")
SettingsPath = os.path.join(ScriptPath, "settings.json")
RedemptionsPath = os.path.join(ScriptPath, "redemptions.json")

APIPath = None
if hasattr(sys, "_MEIPASS"):
    APIPath = os.path.join(sys._MEIPASS, "sheets.v4.json")
else:
    APIPath = os.path.join(ScriptPath, "sheets.v4.json")

CredentialsPath = None 
if hasattr(sys, "_MEIPASS"):
    CredentialsPath = os.path.join(sys._MEIPASS, "credentials.json")
else:
    CredentialsPath = os.path.join(ScriptPath, "credentials.json")

# The ID and range of the spreadsheet.
SPREADSHEET_ID = '1j3DACr9GZ1bsf5MeJWLS9WsWw0JK_YRSEFInxMLWtws'
CELL_RANGE = 'Sheet1!A:C'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def loadRedemptions():
    if RedemptionsPath and os.path.isfile(RedemptionsPath):
        with open(RedemptionsPath, encoding="utf-8-sig", mode="r") as infile:
            return json.load(infile)    #Load the json data

def loadSettings():
    if SettingsPath and os.path.isfile(SettingsPath):
        with codecs.open(SettingsPath, encoding="utf-8-sig", mode="r") as f:
            return json.load(f)

def main():
    settings = {}
    redemptions = {}
    settings = loadSettings()
    redemptions = loadRedemptions()

    print("Script Path is " + ScriptPath)
    print("Getting Spreadsheet ID from " + SettingsPath)
    if "SpreadsheetID" in settings.keys():
        SPREADSHEET_ID = settings["SpreadsheetID"]
    else:
        raise AttributeError("No spreadsheet ID existed in the settings file.")
    print("Spreadsheet ID is " + SPREADSHEET_ID)

    print("Getting Sheet Name.")
    if "Sheet" in settings:
        CELL_RANGE = str(settings["Sheet"]) + "!A:C"
    else:
        raise AttributeError("No Sheet Name existed in the settings file.")
    print("Sheet Name is " + SPREADSHEET_ID)

    print("Iterating over Redemptions.")
    if redemptions is not None and  len(redemptions) > 0:
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("The credentials existed, but needed a refresh.")
                creds.refresh(Request())
            else:
                print("The credentials did not exist or weren't valid.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CredentialsPath, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            print("Saving the credentials to file.")
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                
        print("Getting Sheets v4 API Information.")
        API = None
        if APIPath and os.path.isfile(APIPath):
            with open(APIPath, encoding="utf-8-sig", mode="r") as infile:
                API = json.load(infile)    #Load the json data
        service = build_from_document(API, credentials=creds)

        # Call the Sheets API
        print("Sending request to Google Sheets API.")
        sheet = service.spreadsheets()
        values = [["Username", "Game", "Message"]]
        for redemption in redemptions:
            values.append([redemption["Username"], redemption["Game"], redemption["Message"]])
        for i in range(5):
            values.append(["", "", ""])
        print("Redemption contents: " + str(values))
        body = {"values":values}
        sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=CELL_RANGE,
                              valueInputOption="USER_ENTERED", body=body).execute()
        print("Success?")
    else:
        print("There were no redemptions.")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)