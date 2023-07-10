import pandas as pd
import requests


def download_file(url, local_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def process_df(df):
    """
    # Make the first row the column names and then drop it
    # Drop all rows after column 12
    # Rename the columns in a more readable way
    # Filter all rows looking like ref_row and remove those
    # Filter people who are not working
    # Update indexes
    """
    df.columns = df.iloc[0]
    df = df.iloc[1:]
    df = df.iloc[:, :11]
    df = df.drop('% eve', axis=1)
    df.columns = ['max_shifts', 'hours', 'incoming_shifts', 'date', 'dow', 'name', 'location', 'start', 'end',
                  'availability']

    ref_row = df.iloc[39]
    df = df[~df.apply(lambda row: row.equals(ref_row), axis=1)]
    df['date'] = df['date'].fillna(method='ffill')
    df['dow'] = df['dow'].fillna(method='ffill')

    df = df[df['start'].notna()]
    df = df[df['start'].notnull()]
    df = df[df['end'].notna()]
    df = df[df['end'].notnull()]
    df = df[df.apply(lambda row: type(row['start']) != str or row['start'].strip() != '', axis=1)]
    df = df.reset_index(drop=True)

    return df


def filter_shifts(df, name, from_date):
    my_shifts = df[df['name'] == name]

    if len(my_shifts) == 0:
        return None, None

    if 'date' not in df.columns:
        return None, None

    my_shifts = my_shifts[df['date'] >= from_date]
    if len(my_shifts) == 0:
        return None, None

    others = pd.DataFrame()
    for _, my_shift in my_shifts.iterrows():
        others_same_day_location = df[(df['location'] == my_shift['location']) & (df['date'] == my_shift['date'])]
        others_working_same_shift = others_same_day_location[
            ((others_same_day_location['start'] < my_shift['start']) & (
                    others_same_day_location['end'] > my_shift['start'])) |
            ((others_same_day_location['start'] < my_shift['start']) & (
                    others_same_day_location['end'] >= my_shift['end'])) |
            ((others_same_day_location['start'] > my_shift['start']) & (
                    others_same_day_location['end'] < my_shift['end'])) |
            ((others_same_day_location['start'] < my_shift['end']) & (
                    others_same_day_location['end'] >= my_shift['end']))
            ]
        others = pd.concat([others, others_working_same_shift])

    others.drop_duplicates(inplace=True)
    others = others[others['name'] != name]

    return my_shifts, others



def is_valid_name(name, df):
    return name in df['name'].values
