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

def test_update_event_success(gcal_service):
    gcal_service._service.events.return_value.patch.return_value.execute.return_value = {'id': 'event1'}

    start = datetime.datetime(2026, 4, 26, 10, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2026, 4, 26, 11, 0, tzinfo=datetime.UTC)
    event = gcal_service.update_event("event1", "work", "Updated Event", start, end)

    assert event['id'] == 'event1'
    assert event['calendarId'] == 'work'
    gcal_service._service.events.return_value.patch.assert_called_with(
        calendarId='work',
        eventId='event1',
        body={
            'summary': 'Updated Event',
            'start': {'dateTime': start.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'UTC'},
        }
    )

def test_update_event_error(gcal_service):
    gcal_service._service.events.return_value.patch.return_value.execute.side_effect = Exception("Error")

    result = gcal_service.update_event(
        "event1",
        "primary",
        "Fail",
        datetime.datetime.now(datetime.UTC),
        datetime.datetime.now(datetime.UTC)
    )

    assert result is None

def test_gcal_no_service():
    service = GoogleCalendarService()
    service._service = None
    # Mock authentication to return None
    with patch.object(GoogleCalendarService, '_authenticate'):
        assert service.get_upcoming_events() == []
        assert service.create_event("test", None, None) is None
        assert service.update_event("event1", "primary", "test", None, None) is None

def test_authenticate_with_token_json():
    with patch('services.gcal_service.Credentials') as mock_creds:
        service = GoogleCalendarService(token_json='{"token": "fake"}')
        service._authenticate()
        mock_creds.from_authorized_user_info.assert_called_once()

def test_authenticate_token_refresh():
    with patch('services.gcal_service.Credentials') as mock_creds, \
         patch('services.gcal_service.Request') as mock_request:
        creds = mock_creds.from_authorized_user_info.return_value
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh"

        service = GoogleCalendarService(token_json='{"token": "fake"}')
        service._authenticate()
        creds.refresh.assert_called_with(mock_request.return_value)

def test_authenticate_no_token():
    service = GoogleCalendarService()
    service._authenticate()
    assert service.creds is None


def test_authenticate_invalid_token_json():
    service = GoogleCalendarService(token_json='not-valid-json')
    service._authenticate()
    assert service.creds is None


def test_authenticate_refresh_error():
    with patch('services.gcal_service.Credentials') as mock_creds:
        creds = mock_creds.from_authorized_user_info.return_value
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh"
        creds.refresh.side_effect = Exception("Refresh failed")

        service = GoogleCalendarService(token_json='{"token": "fake"}')
        service._authenticate()
        assert creds.refresh.called


def test_authenticate_build_error():
    with patch('services.gcal_service.Credentials') as mock_creds, \
         patch('services.gcal_service.build') as mock_build:
        mock_creds.from_authorized_user_info.return_value.valid = True
        mock_build.side_effect = Exception("Build failed")

        service = GoogleCalendarService(token_json='{"token": "fake"}')
        service._authenticate()
        assert service._service is None


def test_gcal_service_for_token():
    from services.gcal_service import gcal_service_for_token
    service = gcal_service_for_token('{"test": true}')
    assert isinstance(service, GoogleCalendarService)
    assert service.token_json == '{"test": true}'
