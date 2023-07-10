from flask import Flask, request, redirect, session, render_template
from functools import wraps
import pandas as pd
import src.utils as utils
import src.calendar_setup as calendar
from requests_oauthlib import OAuth2Session
from os import getenv

global df

# OAuth2 variables
OAUTH2_CLIENT_ID = getenv('OAUTH2_CLIENT_ID')
OAUTH2_CLIENT_SECRET = getenv('OAUTH2_CLIENT_SECRET')
OAUTH2_REDIRECT_URI = getenv('OAUTH2_REDIRECT_URI')

AUTHORIZATION_BASE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URI = 'https://oauth2.googleapis.com/token'
SCOPE = ['https://www.googleapis.com/auth/calendar']


# Wrap a function with this decorator to ensure the user is logged in
def requires_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'oauth_token' not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated


def retrieve_and_process_data():
    global df
    utils.download_file('https://dl.dropboxusercontent.com/s/pmbbmqs3jm54n8o/staff%20schedule%20vers13.xlsx',
                        'schedule.xlsx')

    # Load the DataFrame
    df = pd.read_excel('schedule.xlsx', engine='openpyxl')

    # Process the DataFrame
    df = utils.process_df(df)


def create_app():
    application = Flask(__name__)
    retrieve_and_process_data()
    return application


app = create_app()
app.secret_key = getenv('FLASK_SECRET_KEY')


@app.route('/', methods=['GET', 'POST'])
def form():
    logged_in = 'oauth_token' in session
    error_message = None
    success = False

    if request.method == 'POST':
        name = request.form.get('name')
        start_date = request.form.get('start_date')
        if not utils.is_valid_name(name, df):
            error_message = 'Invalid name. Please try again.'
        else:
            my_shifts, others = utils.filter_shifts(df, name, start_date)
            if my_shifts is None:
                error_message = 'No shifts available for the given date.'
            else:
                # Store the values in the session
                session['name'] = name
                session['start_date'] = start_date

                # Create the calendar and events only if the user has logged in
                if logged_in:
                    # Create the calendar
                    try:
                        service = calendar.setup_google_api(session['oauth_token'])
                    except ValueError as e:
                        if str(e) == "Refresh token missing":
                            return redirect('/login')
                        else:
                            raise e

                    # Create the events
                    try:
                        calendar.create_calendar_events(service, my_shifts, others)
                        success = True
                    except Exception as e:
                        error_message = 'An error occurred while creating the calendar events. ' \
                                        'Please contact the developer and explain the steps you have taken.' \
                                        'Mention the following error message: ' + str(e) + '.'

                    if success:
                        return render_template('success.html', name=name)
                    else:
                        return render_template('index.html', logged_in=logged_in, error_message=error_message)
                else:
                    return redirect('/login')  # Redirect user to login if they haven't logged in yet

    name = session.get('name', '')
    start_date = session.get('start_date', '')

    # Render the form
    return render_template('index.html', logged_in=logged_in, error_message=error_message, name=name,
                           start_date=start_date)


@app.route('/login')
def login():
    google = OAuth2Session(OAUTH2_CLIENT_ID, redirect_uri=OAUTH2_REDIRECT_URI, scope=SCOPE)
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL,
                                                        access_type='offline',
                                                        prompt='consent')
    session['oauth_state'] = state
    return redirect(authorization_url)


@app.route('/logout')
def logout():
    # Remove the user information from the session
    session.pop('oauth_token', None)
    session.pop('logged_in', None)
    # Redirect the user to the main page
    return redirect('/')


@app.route('/callback')
def callback():
    google = OAuth2Session(OAUTH2_CLIENT_ID, redirect_uri=OAUTH2_REDIRECT_URI, state=session['oauth_state'],
                           token=session.get('oauth_token'))
    token = google.fetch_token(TOKEN_URI, client_secret=OAUTH2_CLIENT_SECRET, authorization_response=request.url,
                               include_client_id=True)
    session['oauth_token'] = token

    # Store form data if it exists in session
    if 'name' in session and 'start_date' in session:
        name = session['name']
        start_date = session['start_date']
        my_shifts, others = utils.filter_shifts(df, name, start_date)
        if my_shifts is not None:
            # Create the calendar
            try:
                service = calendar.setup_google_api(session['oauth_token'])
            except ValueError as e:
                if str(e) == "Refresh token missing":
                    return redirect('/login')
                else:
                    raise e

            # Create the events
            try:
                calendar.create_calendar_events(service, my_shifts, others)
                success = True
            except Exception as e:
                error_message = 'An error occurred while creating the calendar events. ' \
                                'Please contact the developer and explain the steps you have taken.' \
                                'Mention the following error message: ' + str(e) + '.'
            if success:
                return render_template('success.html', name=name)
            else:
                return render_template('index.html', logged_in=True, error_message=error_message, name=name,
                                       start_date=start_date)
    return redirect('/')


@app.route('/calendar')
@requires_login
def calendar_view():
    google = OAuth2Session(OAUTH2_CLIENT_ID, token=session['oauth_token'])
    response = google.get('https://www.googleapis.com/calendar/v3/users/me/calendarList')

    return response.content  # This will show the user's calendars


@app.route('/delete_events', methods=['POST'])
@requires_login
def delete_events():
    if request.method == 'POST':
        # Create the calendar
        try:
            service = calendar.setup_google_api(session['oauth_token'])
        except ValueError as e:
            if str(e) == "Refresh token missing":
                return redirect('/login')
            else:
                raise e
        calendar.delete_calendar_events(service)
        return redirect('/')  # Redirect to the homepage or any other desired page


if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)
