import sys
import datetime
import requests
import math


def get_all_updated_records_since_date(date, verbose=False):
    """
    Returns all inspire ids of records updated since the specified date (YYYY-MM-DD).
    Alternatively, date can be a number, denoting days since today (-1 = yesterday).
    Only records updated on that specific date will then be returned.
    """

    date_is_delta_from_today = (type(date) is int or type(date) is str and date.isdigit())

    if verbose:
        if date_is_delta_from_today:
            print("Obtaining inspire ids of records updated {} days ago.".format(abs(int(date))))
        else:
            print("Obtaining inspire ids of records updated since {}.".format(date))

    if date_is_delta_from_today:
        specified_time = datetime.datetime.today() + datetime.timedelta(days=-int(date))
    else:
        specified_time = datetime.datetime.strptime(date, "%Y-%m-%d")

    page = 1
    counter = 0
    ids = []

    while page < 1000:

        if date_is_delta_from_today:
            response = requests.get("https://inspirehep.net/api/literature?q=external_system_identifiers.schema:HEPData%20and%20du%20today-{}&page={}".format(date, page))
        else:
            response = requests.get("http://inspirehep.net/api/literature?q=external_system_identifiers.schema:HEPData&page={}".format(page))

        total = response.json()['hits']['total']

        if response.status_code != 200 or len(response.json()['hits']['hits']) == 0:
            break
        else:
            page += 1

        if verbose:
            print("\rAt page {}/{}.".format(page - 1, math.ceil(total / 10.)), end="")

        for i, hit in enumerate(response.json()['hits']['hits']):

            if date_is_delta_from_today:
                ids += [hit['id']]
            else:
                counter += 1
                updated_time = datetime.datetime.strptime(hit['updated'].split('T')[0], "%Y-%m-%d")
                if updated_time > specified_time:
                    ids += [hit['id']]

    if verbose:
        if date_is_delta_from_today:
            print("\r{} records were updated {} days ago.".format(len(ids), abs(int(date))))
        else:
            print("\rChecked {} records. {} were updated since {}.".format(counter, len(ids), date))

    return ids


if __name__ == "__main__":
    print(get_all_updated_records_since_date(sys.argv[1], verbose=True))
