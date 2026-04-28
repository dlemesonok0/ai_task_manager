import pytest
import datetime
from unittest.mock import patch, MagicMock
from services.gcal_service import GoogleCalendarService

@pytest.fixture
def gcal_service():
    with patch('services.gcal_service.build') as mock_build:
        service = GoogleCalendarService()
        service._service = mock_build.return_value
        return service

def test_get_upcoming_events_success(gcal_service):
    gcal_service._service.calendarList.return_value.list.return_value.execute.return_value = {
        'items': [{'id': 'primary'}]
    }
    gcal_service._service.events.return_value.list.return_value.execute.return_value = {
        'items': [
            {
                'summary': 'Meeting',
                'start': {'dateTime': '2026-04-26T10:00:00Z'},
                'end': {'dateTime': '2026-04-26T11:00:00Z'}
            }
        ]
    }
    
    events = gcal_service.get_upcoming_events()
    assert len(events) == 1
    assert events[0]['summary'] == 'Meeting'
    assert events[0]['calendarId'] == 'primary'

def test_get_upcoming_events_from_all_calendars(gcal_service):
    gcal_service._service.calendarList.return_value.list.return_value.execute.return_value = {
        'items': [{'id': 'primary'}, {'id': 'work'}, {'id': 'deleted', 'deleted': True}]
    }

    def event_result(calendarId, **kwargs):
        events_by_calendar = {
            'primary': [
                {
                    'summary': 'Primary Meeting',
                    'start': {'dateTime': '2026-04-26T12:00:00Z'},
                    'end': {'dateTime': '2026-04-26T13:00:00Z'}
                }
            ],
            'work': [
                {
                    'summary': 'Work Standup',
                    'start': {'dateTime': '2026-04-26T09:00:00Z'},
                    'end': {'dateTime': '2026-04-26T09:30:00Z'}
                }
            ]
        }
        result = MagicMock()
        result.execute.return_value = {'items': events_by_calendar[calendarId]}
        return result

    gcal_service._service.events.return_value.list.side_effect = event_result

    events = gcal_service.get_upcoming_events(max_results=10)

    assert [event['summary'] for event in events] == ['Work Standup', 'Primary Meeting']
    assert [event['calendarId'] for event in events] == ['work', 'primary']
    assert gcal_service._service.events.return_value.list.call_count == 2

def test_get_upcoming_events_error(gcal_service):
    gcal_service._service.calendarList.return_value.list.return_value.execute.return_value = {
        'items': [{'id': 'primary'}]
    }
    gcal_service._service.events.return_value.list.return_value.execute.side_effect = Exception("Auth Error")
    events = gcal_service.get_upcoming_events()
    assert events == []

def test_create_event_success(gcal_service):
    gcal_service._service.events.return_value.insert.return_value.execute.return_value = {'id': 'new_event_id'}
    
    start = datetime.datetime(2026, 4, 26, 10, 0)
    end = datetime.datetime(2026, 4, 26, 11, 0)
    event = gcal_service.create_event("Test Event", start, end)
    assert event['id'] == 'new_event_id'

def test_create_event_error(gcal_service):
    gcal_service._service.events.return_value.insert.return_value.execute.side_effect = Exception("Error")
    result = gcal_service.create_event("Fail", datetime.datetime.now(), datetime.datetime.now())
    assert result is None

def test_gcal_no_service():
    service = GoogleCalendarService()
    service._service = None
    # Mock authentication to return None
    with patch.object(GoogleCalendarService, '_authenticate'):
        assert service.get_upcoming_events() == []
        assert service.create_event("test", None, None) is None

def test_authenticate_existing_token():
    with patch('os.path.exists', return_value=True):
        with patch('services.gcal_service.Credentials') as mock_creds:
            service = GoogleCalendarService()
            service._authenticate()
            mock_creds.from_authorized_user_file.assert_called()

def test_authenticate_refresh_token():
    with patch('os.path.exists', return_value=True):
        with patch('services.gcal_service.Credentials') as mock_creds, \
             patch('services.gcal_service.Request') as mock_request:
            creds = mock_creds.from_authorized_user_file.return_value
            creds.valid = False
            creds.expired = True
            creds.refresh_token = "refresh"
            creds.to_json.return_value = '{"token": "fake"}'
            
            service = GoogleCalendarService()
            with patch('builtins.open', MagicMock()):
                service._authenticate()
                creds.refresh.assert_called_with(mock_request.return_value)

def test_authenticate_refresh_error():
    with patch('os.path.exists', return_value=True):
        with patch('services.gcal_service.Credentials') as mock_creds:
            creds = mock_creds.from_authorized_user_file.return_value
            creds.valid = False
            creds.expired = True
            creds.refresh_token = "refresh"
            creds.refresh.side_effect = Exception("Refresh failed")
            
            service = GoogleCalendarService()
            service._authenticate()
            assert service.creds is None

def test_authenticate_new_flow():
    with patch('os.path.exists') as mock_exists:
        mock_exists.side_effect = lambda x: x.endswith('credentials.json')
        with patch('services.gcal_service.InstalledAppFlow') as mock_flow:
            flow = mock_flow.from_client_secrets_file.return_value
            flow.run_local_server.return_value = MagicMock()
            
            service = GoogleCalendarService()
            with patch('builtins.open', MagicMock()):
                service._authenticate()
                flow.run_local_server.assert_called()

def test_authenticate_new_flow_error():
    with patch('os.path.exists') as mock_exists:
        mock_exists.side_effect = lambda x: x.endswith('credentials.json')
        with patch('services.gcal_service.InstalledAppFlow') as mock_flow:
            flow = mock_flow.from_client_secrets_file.return_value
            flow.run_local_server.side_effect = Exception("Flow failed")
            
            service = GoogleCalendarService()
            service._authenticate()
            assert service.creds is None

def test_authenticate_no_creds_file():
    with patch('os.path.exists', return_value=False):
        service = GoogleCalendarService()
        service._authenticate()
        assert service.creds is None
