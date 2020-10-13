"""Update INSPIRE publication information."""

import datetime
import math

from hepdata.modules.records.utils.doi_minter import generate_dois_for_submission
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.workflow import update_record
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.ext.elasticsearch.api import index_record_ids, push_data_keywords
from hepdata.modules.email.api import notify_publication_update
from hepdata.resilient_requests import resilient_requests

from celery import shared_task
import logging

logging.basicConfig()
log = logging.getLogger(__name__)


RECORDS_PER_PAGE = 10


@shared_task
def update_record_info(inspire_id, send_email=False):
    """Update publication information from INSPIRE for a specific record."""

    if inspire_id is None:
        log.error("Inspire ID is None")
        return 'Inspire ID is None'

    inspire_id = inspire_id.replace("ins", "")

    hep_submission = get_latest_hepsubmission(inspire_id=inspire_id)
    if hep_submission is None:
        log.warning("Failed to retrieve HEPData submission for Inspire ID {0}".format(inspire_id))
        return 'No HEPData submission'

    publication_recid = hep_submission.publication_recid

    log.info("Updating recid {} with information from Inspire record {}".format(publication_recid, inspire_id))

    updated_inspire_record_information, status = get_inspire_record_information(inspire_id)

    if status == 'success':

        # Also need to update publication information for data records.
        data_submissions = DataSubmission.query.filter_by(
            publication_recid=publication_recid, version=hep_submission.version
        ).order_by(DataSubmission.id.asc())
        record_ids = [publication_recid]  # list of record IDs
        for data_submission in data_submissions:
            record_ids.append(data_submission.associated_recid)

        same_information = {}
        for index, recid in enumerate(record_ids):

            if index == 0:
                updated_record_information = updated_inspire_record_information
            else:
                # Only update selected keys for data records.
                updated_record_information = {
                    key: updated_inspire_record_information[key] for key in (
                        'authors', 'creation_date', 'journal_info', 'collaborations'
                    )
                }

            record_information = get_record_by_id(recid)
            same_information[recid] = True
            for key, value in updated_record_information.items():
                if key not in record_information or record_information[key] != value:
                    log.debug('For recid {}, key {} has new value {}'.format(recid, key, value))
                    same_information[recid] = False
                    update_record(recid, updated_record_information)
                    break
            log.info('For recid {}, information needs to be updated: {}'.format(recid, str(not(same_information[recid]))))

        if all(same for same in same_information.values()):
            return 'No update needed'

    else:
        log.warning("Failed to retrieve publication information for Inspire record {0}".format(inspire_id))
        return 'Invalid Inspire ID'

    if hep_submission.overall_status == 'finished':
        index_record_ids(record_ids)  # index for Elasticsearch
        push_data_keywords(pub_ids=[recid])
        generate_dois_for_submission.delay(inspire_id=inspire_id)  # update metadata stored in DataCite
        if send_email:
            record_information = get_record_by_id(publication_recid)
            notify_publication_update(hep_submission, record_information)   # send email to all participants

    return 'Success'


@shared_task
def update_records_info_since(date):
    """Update publication information from INSPIRE for all records updated *since* a certain date."""
    inspire_ids = get_inspire_records_updated_since(date)
    for inspire_id in inspire_ids:
        status = update_record_info.delay(inspire_id)
        log.info('Updated Inspire ID {} with status: {}'.format(inspire_id, status))


@shared_task
def update_records_info_on(date):
    """Update publication information from INSPIRE for all records updated *on* a certain date."""
    inspire_ids = get_inspire_records_updated_on(date)
    for inspire_id in inspire_ids:
        status = update_record_info.delay(inspire_id)
        log.info('Updated Inspire ID {} with status: {}'.format(inspire_id, status))


@shared_task
def update_all_records_info():
    """Update publication information from INSPIRE for *all* records."""
    inspire_ids = get_inspire_records_updated_since('1899-01-01')
    for inspire_id in inspire_ids:
        status = update_record_info.delay(inspire_id)
        log.info('Updated Inspire ID {} with status: {}'.format(inspire_id, status))


def get_inspire_records_updated_since(date):
    """Returns all inspire records updated since YYYY-MM-DD or #int as number of days since today (1 = yesterday)"""
    return _get_inspire_records_updated('since', date)


def get_inspire_records_updated_on(date):
    """Returns all inspire records updated on YYYY-MM-DD or #int as number of days since today (1 = yesterday)."""
    return _get_inspire_records_updated('on', date)


def _get_inspire_records_updated(on_or_since, date):
    """Returns a list of Inspire IDs of records with HEPData modified on or since a certain date."""

    specified_time = _get_time(date)

    log.info("Obtaining Inspire IDs of records updated {} {}.".format(on_or_since, specified_time.strftime('%Y-%m-%d')))

    url = _get_url(1, specified_time, on_or_since)
    response = resilient_requests('get', url)
    response.raise_for_status()

    total_hits = response.json()['hits']['total']
    total_pages = math.ceil(total_hits / RECORDS_PER_PAGE)

    log.info("{} records were updated {} {}.".format(total_hits, on_or_since, specified_time.strftime('%Y-%m-%d')))

    ids = []

    for page in range(1, total_pages + 1):

        log.debug("At page {}/{}.".format(page, total_pages))

        url = _get_url(page, specified_time, on_or_since)
        response = resilient_requests('get', url)
        response.raise_for_status()

        for i, hit in enumerate(response.json()['hits']['hits']):
            ids += [hit['id']]

    return ids


def _get_time(date):
    """Returns a datetime object from either a string YYYY-MM-DD or integer (interpreted as number of past days)."""

    date_is_int = (type(date) is int or type(date) is str and date.isdigit())

    if date_is_int:
        specified_time = datetime.datetime.today() + datetime.timedelta(days=-abs(int(date)))
    else:
        specified_time = datetime.datetime.strptime(date, "%Y-%m-%d")

    return specified_time


def _get_url(page, specified_time, on_or_since):
    """Returns an INSPIRE API query URL for records with HEPData modified on or since a certain date."""

    size = RECORDS_PER_PAGE
    url = ('https://inspirehep.net/api/literature?sort=mostrecent&size={}&page={}'.format(size, page) +
           '&q=external_system_identifiers.schema%3AHEPData%20and%20legacy_version%3A{}%2'.format(specified_time.strftime("%Y%m%d")) +
           ('A' if on_or_since == 'on' else 'B'))
    return url
