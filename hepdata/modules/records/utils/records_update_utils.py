import datetime
import requests
import math

from hepdata.modules.records.utils.doi_minter import generate_dois_for_submission
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.workflow import update_record
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.ext.elasticsearch.api import index_record_ids
from hepdata.modules.email.api import notify_publication_update


def update_record_info(inspire_id, recid='', send_email=False):
    inspire_id = inspire_id.replace("ins", "")

    if recid == '':
        hep_submission = get_latest_hepsubmission(inspire_id=inspire_id)
        if hep_submission is None:
            print("Failed to retrieve hep submission for {0}".format(inspire_id))
            return
        recid = hep_submission.publication_recid

    updated_record_information, status = get_inspire_record_information(inspire_id)

    if status == 'success':
        record_information = update_record(recid, updated_record_information)
    else:
        print("Failed to retrieve publication information for {0}".format(inspire_id))
        return

    if recid == '' and hep_submission.overall_status == 'finished':
        index_record_ids([record_information["recid"]])
        generate_dois_for_submission.delay(inspire_id=inspire_id)  # update metadata stored in DataCite
        if send_email:
            notify_publication_update(hep_submission, record_information)   # send email to all participants


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
