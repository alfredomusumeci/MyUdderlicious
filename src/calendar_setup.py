from datetime import datetime, time, timezone, timedelta
from google.oauth2 import credentials
from googleapiclient.discovery import build

EVENT_NAME = 'Udderlicious Shift'


# Function to set up google API
def setup_google_api(token):
    # Check if 'refresh_token' is in the token dictionary
    if 'refresh_token' in token:
        creds = credentials.Credentials(
            token['access_token'],
            refresh_token=token['refresh_token'],
        )
    else:
        # Raise a specific exception if refresh_token is not present
        raise ValueError("Refresh token missing")

    return build('calendar', 'v3', credentials=creds)


# Function to create calendar events
# If the event already exists, it will be updated
def create_calendar_events(service, my_shifts, result):
    primary_calendar_id = get_primary_calendar(service)

    for _, my_shift in my_shifts.iterrows():
        my_shift_event = {
            'summary': EVENT_NAME,
            'location': my_shift['location'],
            'description': '\n'.join([f'{row["name"]}: {row["start"]} - {row["end"]}' for _, row in
                                      result[result['date'] == my_shift['date']].iterrows()]),
            'start': {
                'dateTime': my_shift['date'].strftime('%Y-%m-%d') + 'T' + my_shift['start'].strftime('%H:%M:%S'),
                'timeZone': 'Europe/London',
            },
            'end': {
                'dateTime': my_shift['date'].strftime('%Y-%m-%d') + 'T' + my_shift['end'].strftime('%H:%M:%S'),
                'timeZone': 'Europe/London',
            },
        }

        # Check if event already exists
        # Obtain events only within the same day
        start_datetime = datetime.combine(my_shift['date'], time.min).replace(tzinfo=timezone.utc).isoformat()
        end_datetime = datetime.combine(my_shift['date'], time.max).replace(tzinfo=timezone.utc).isoformat()
        events = service.events().list(
            calendarId=primary_calendar_id,
            timeMin=start_datetime,
            timeMax=end_datetime,
        ).execute()

        event_exists = False
        existing_event_id = None
        for event in events['items']:
            if 'dateTime' not in event['start']:
                continue
            else:
                event_start = datetime.strptime(event['start']['dateTime'], '%Y-%m-%dT%H:%M:%S%z').strftime('%H:%M')
                if event_start == my_shift['start'].strftime('%H:%M'):
                    event_exists = True
                    existing_event_id = event['id']
                    break

        if event_exists:
            created_event = service.events().update(calendarId=primary_calendar_id, eventId=existing_event_id,
                                                    body=my_shift_event).execute()
        else:
            created_event = service.events().insert(calendarId=primary_calendar_id, body=my_shift_event).execute()


# Function to delete all calendar events
def delete_calendar_events(service):
    primary_calendar_id = get_primary_calendar(service)

    two_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=2)
    two_weeks_ago_iso = two_weeks_ago.isoformat()

    page_token = None
    while True:
        events = service.events().list(
            calendarId=primary_calendar_id,
            timeMin=two_weeks_ago_iso,
            pageToken=page_token
        ).execute()

        for event in events['items']:
            if event.get('summary') == EVENT_NAME:
                service.events().delete(calendarId=primary_calendar_id, eventId=event['id']).execute()

        page_token = events.get('nextPageToken')
        if not page_token:
            break


def get_primary_calendar(service):
    # Retrieve the primary calendar ID
    calendar_list = service.calendarList().list().execute()
    primary_calendar_id = None
    for calendar in calendar_list['items']:
        if calendar.get('primary'):
            primary_calendar_id = calendar['id']
            break
    if primary_calendar_id is None:
        raise ValueError("Primary calendar not found.")
    return primary_calendar_id
