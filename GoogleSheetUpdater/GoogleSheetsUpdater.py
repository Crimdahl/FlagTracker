from __future__ import print_function
import os.path, sys, codecs, json
from googleapiclient.discovery import build_from_document
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

ScriptPath = os.path.dirname(__file__)
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

print(str(CredentialsPath))

# The ID and range of the spreadsheet.
SPREADSHEET_ID = '1j3DACr9GZ1bsf5MeJWLS9WsWw0JK_YRSEFInxMLWtws'
CELL_RANGE = 'Sheet1!A:C'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class Settings(object):
    def __init__(self, SettingsPath=None):
        if SettingsPath and os.path.isfile(SettingsPath):
            with codecs.open(SettingsPath, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f)


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
    if "spreadsheetId" in settings:
        SPREADSHEET_ID = settings["spreadsheetId"]
    else:
        raise AttributeError("No spreadsheet ID existed in the settings file.")
    
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
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CredentialsPath, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        #service = build(serviceName='sheets', version='v4', discoveryServiceUrl="https://sheets.googleapis.com/$discovery/rest?version=v4",
        #                credentials=creds,                        
        #                cache_discovery=False)
        API = None
        if APIPath and os.path.isfile(APIPath):
            with open(APIPath, encoding="utf-8-sig", mode="r") as infile:
                API = json.load(infile)    #Load the json data
        service = build_from_document(API, credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()

        values = [["Username", "Game", "Message"]]
        for redemption in redemptions:
            values.append([redemption["Username"], redemption["Game"], redemption["Message"]])
        for i in range(20):
            values.append(["", "", ""])

        body = {"values":values}


        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=CELL_RANGE,
                                       valueInputOption="USER_ENTERED", body=body).execute()

if __name__ == '__main__':
    main()