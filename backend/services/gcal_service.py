import os
import datetime
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def __init__(self):
        self.creds = None
        self._service = None
        self.credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials.json")

    @property
    def service(self):
        if self._service is None:
            self._authenticate()
        return self._service

    def _authenticate(self):
        """Authenticate with Google Calendar API using OAuth2."""
        token_path = os.path.join(os.path.dirname(__file__), '..', 'token.json')
        creds_path = os.path.join(os.path.dirname(__file__), '..', self.credentials_file)

        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        # We handle the case where credentials.json might not exist yet to avoid crashing the server.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing Google Calendar token: {e}")
                    self.creds = None
            elif os.path.exists(creds_path):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    # This will open a browser window for authentication if running locally
                    self.creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error initializing Google Calendar OAuth flow: {e}")
                    self.creds = None
            else:
                print(f"WARNING: Google Calendar credentials file '{self.credentials_file}' not found. Calendar sync is disabled.")
                return

            if self.creds:
                # Save the credentials for the next run
                with open(token_path, 'w') as token:
                    token.write(self.creds.to_json())

        if self.creds:
            try:
                self._service = build('calendar', 'v3', credentials=self.creds)
            except Exception as e:
                print(f"Error building Google Calendar service: {e}")
                self._service = None

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fetch upcoming events from the primary calendar."""
        if not self.service:
            return []
        
        try:
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = self.service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=max_results, singleEvents=True,
                orderBy='startTime').execute()
            events = events_result.get('items', [])
            return events
        except Exception as e:
            print(f"Error fetching Google Calendar events: {e}")
            return []

    def create_event(self, summary: str, start_time: datetime.datetime, end_time: datetime.datetime, description: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new event in the primary calendar."""
        if not self.service:
            return None
        
        event = {
            'summary': summary,
            'description': description or '',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
        }

        try:
            created_event = self.service.events().insert(calendarId='primary', body=event).execute()
            return created_event
        except Exception as e:
            print(f"Error creating Google Calendar event: {e}")
            return None

# Create a singleton instance (Note: authenticates on import if credentials.json is present)
gcal_service = GoogleCalendarService()
