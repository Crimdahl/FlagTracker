pyinstaller GoogleSheetsWorker.py -F -n GoogleSheetsUpdater --add-data "credentials.json;." --add-data "sheets.v4.json;."