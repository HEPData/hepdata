import os

from celery import shared_task
from flask import render_template
from invenio_db import db
from invenio_pidstore.models import PersistentIdentifier

from invenio_pidstore.providers.datacite import DataCiteProvider
from sqlalchemy.orm.exc import NoResultFound

from hepdata.config import TEST_DOI_PREFIX
from hepdata.modules.records.models import DataSubmission, HEPSubmission
from hepdata.modules.records.utils.common import get_record_by_id


@shared_task
def generate_xml_for_submission(recid, version):
    data_submissions = DataSubmission.query.filter_by(publication_recid=recid, version=version).order_by(
        DataSubmission.id.asc())

    hep_submission = HEPSubmission.query.filter_by(publication_recid=recid)
    publication_info = get_record_by_id(recid)

    xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                          doi=hep_submission.doi,
                          overall_submission=hep_submission,
                          data_submissions=data_submissions,
                          publication_info=publication_info)

    # Register DOI for the version, and update the base DOI to resolve to the latest submission version.
    register_doi(hep_submission.doi, 'http://www.hepdata.net/record/ins{0}'.format(publication_info.inspire_id),
                 xml, publication_info['uuid'])

    register_doi(hep_submission.doi+".v{0}".format(hep_submission.latest_version),
                 'http://www.hepdata.net/record/ins{0}?version={1}'
                 .format(publication_info.inspire_id, hep_submission.latest_version),
                 xml, publication_info['uuid'])


@shared_task
def generate_doi_for_data_submission(data_submission_id, version):
    data_submission = DataSubmission.query.filter_by(id=data_submission_id).first()

    hep_submission = HEPSubmission.query.filter_by(publication_recid=data_submission.publication_recid)

    publication_info = get_record_by_id(data_submission.publication_recid)

    xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                          doi=data_submission.doi,
                          overall_submission=hep_submission,
                          data_submission=data_submission, licenses=[],
                          publication_info=publication_info)

    register_doi(data_submission.doi, 'http://www.hepdata.net/record/{0}'.format(data_submission.associated_recid),
                 xml, publication_info['uuid'])


def reserve_doi_for_hepsubmission(hepsubmission):
    base_doi = "{0}/hepdata.{1}".format(
        TEST_DOI_PREFIX, hepsubmission.publication_recid)

    version = hepsubmission.latest_version
    if version == 0: version += 1

    if hepsubmission.latest_version == 0:
        # creating a DOI for the first time
        version += 1

    create_doi(base_doi)


def reserve_dois_for_data_submissions(publication_recid, version):
    """
    Reserves a DOI for a data submission and saves to the datasubmission object.
    :param data_submission: DataSubmission object representing a data table.
    :return:
    """

    data_submissions = DataSubmission.query.filter_by(publication_recid=publication_recid, version=version) \
        .order_by(DataSubmission.id.asc())

    for index, data_submission in enumerate(data_submissions):
        # using the index of the sorted submissions should do a good job of maintaining the order of the tables.
        doi_value = "{0}/hepdata.{1}.v{2}/t{3}".format(
            TEST_DOI_PREFIX, publication_recid, data_submission.version + 1, (index + 1))

        create_doi(doi_value)
        data_submission.doi = doi_value

        db.session.add(data_submission)
    db.session.commit()


def create_doi(doi):
    """
    :param doi: Creates a DOI using the data provider.
    :return:
    """
    return DataCiteProvider.create(doi, 'doi')


def register_doi(doi, url, xml, uuid):
    """
    Given a data submission id, this method takes it's assigned DOI, creates the DataCite XML,
    and registers the DOI.
    :param data_submissions:
    :param recid:
    :return:
    """
    try:
        provider = DataCiteProvider.get(doi, 'doi')
    except NoResultFound:
        provider = create_doi(doi)

    pidstore_obj = PersistentIdentifier.query.filter_by(pid_value=doi)
    pidstore_obj.object_uuid = uuid
    db.session.add(pidstore_obj)
    db.session.commit()

    provider.register(url, xml)
