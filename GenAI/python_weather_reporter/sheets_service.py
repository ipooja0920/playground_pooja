import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']

def get_sheets_service():
    """Shows basic usage of the Sheets API."""
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found. Please provide Google Cloud client secrets.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        return service, drive_service
    except HttpError as err:
        print(err)
        return None

def create_or_get_spreadsheet(service, drive_service, title="Storrs AI Weather Data"):
    """Creates a spreadsheet or returns the ID of an existing one."""
    try:
        # Check if file exists in Drive
        query = f"name = '{title}' and mimeType = 'application/vnd.google-apps.spreadsheet'"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])

        if items:
            print(f"Spreadsheet found: {items[0]['id']}")
            return items[0]['id']
        
        # Create new spreadsheet
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        
        # Add Headers
        headers = [['Date', 'Condition', 'Temp (C)', 'High (C)', 'Low (C)', 'Sunny', 'Rainy', 'Stormy', 'Snowy']]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body={'values': headers}
        ).execute()

        print(f"Spreadsheet created: {spreadsheet_id}")
        return spreadsheet_id

    except HttpError as err:
        print(err)
        return None

def append_weather_data(service, spreadsheet_id, data):
    """Appends weather data to the spreadsheet."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        now,
        data['condition'],
        data['temp_c'],
        data['high_c'],
        data['low_c'],
        data['is_sunny'],
        data['is_rainy'],
        data['is_stormy'],
        data['is_snowy']
    ]
    
    body = {
        'values': [row]
    }
    
    try:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A:A',
            valueInputOption='RAW',
            body=body
        ).execute()
        print("Data successfully appended to spreadsheet.")
    except HttpError as err:
        print(err)

if __name__ == "__main__":
    # Test script - requires credentials.json
    res = get_sheets_service()
    if res:
        sheet_service, drive_service = res
        sid = create_or_get_spreadsheet(sheet_service, drive_service)
        if sid:
            from weather_service import get_weather
            weather_data = get_weather()
            if weather_data:
                append_weather_data(sheet_service, sid, weather_data)
