import logging
import datetime
import json
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def __init__(self, token_json: str | None = None):
        self.creds = None
        self._service = None
        self.token_json = token_json

    @property
    def service(self):
        if self._service is None:
            self._authenticate()
        return self._service

    def _authenticate(self):
        if self.token_json:
            try:
                self.creds = Credentials.from_authorized_user_info(json.loads(self.token_json), SCOPES)
            except Exception:
                logger.exception("Error loading user Google token JSON")
                self.creds = None

        if self.creds and not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception:
                    logger.exception("Error refreshing Google Calendar token")
                    self.creds = None
            else:
                logger.warning("Google Calendar token is invalid and cannot be refreshed")
                self.creds = None

        if self.creds:
            try:
                self._service = build('calendar', 'v3', credentials=self.creds)
            except Exception:
                logger.exception("Error building Google Calendar service")
                self._service = None

    def _get_event_start_value(self, event: Dict[str, Any]) -> str:
        start = event.get('start', {})
        return start.get('dateTime') or start.get('date') or ''

    def _get_calendar_ids(self) -> List[str]:
        calendars_result = self.service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        calendar_ids = [
            calendar['id']
            for calendar in calendars
            if calendar.get('id') and not calendar.get('deleted')
        ]
        return calendar_ids or ['primary']

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fetch upcoming events from all calendars available to the account."""
        if not self.service:
            return []
        
        try:
            now = datetime.datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
            events = []

            for calendar_id in self._get_calendar_ids():
                events_result = self.service.events().list(
                    calendarId=calendar_id, timeMin=now,
                    maxResults=max_results, singleEvents=True,
                    orderBy='startTime').execute()
                for event in events_result.get('items', []):
                    event['calendarId'] = calendar_id
                    events.append(event)

            events.sort(key=self._get_event_start_value)
            return events[:max_results]
        except Exception:
            logger.exception("Error fetching Google Calendar events")
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
        except Exception:
            logger.exception("Error creating Google Calendar event")
            return None

    def update_event(
        self,
        event_id: str,
        calendar_id: str,
        summary: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime
    ) -> Optional[Dict[str, Any]]:
        """Update an existing event in the specified calendar."""
        if not self.service:
            return None

        event = {
            'summary': summary,
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
            updated_event = self.service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            updated_event['calendarId'] = calendar_id
            return updated_event
        except Exception:
            logger.exception("Error updating Google Calendar event")
            return None

# Create a singleton instance (Note: authenticates on import if credentials.json is present)
gcal_service = GoogleCalendarService()


def gcal_service_for_token(token_json: str | None) -> GoogleCalendarService:
    return GoogleCalendarService(token_json=token_json)
