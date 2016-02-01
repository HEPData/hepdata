import os

from celery import shared_task
from flask import render_template, current_app
from invenio_db import db
from invenio_pidstore.errors import PIDInvalidAction, PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier

from invenio_pidstore.providers.datacite import DataCiteProvider

from hepdata.config import TEST_DOI_PREFIX
from hepdata.modules.records.models import DataSubmission, HEPSubmission, DataResource, License
from hepdata.modules.records.utils.common import get_record_by_id, encode_string, decode_string


@shared_task
def generate_doi_for_submission(recid, version):
    data_submissions = DataSubmission.query.filter_by(publication_recid=recid, version=version).order_by(
        DataSubmission.id.asc())

    hep_submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
    publication_info = get_record_by_id(recid)

    version_doi = hep_submission.doi + ".v{0}".format(hep_submission.latest_version)

    base_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                               doi=hep_submission.doi,
                               overall_submission=hep_submission,
                               data_submissions=data_submissions,
                               publication_info=publication_info)

    version_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                                  doi=version_doi,
                                  overall_submission=hep_submission,
                                  data_submissions=data_submissions,
                                  publication_info=publication_info)

    # Register DOI for the version, and update the base DOI to resolve to the latest submission version.
    register_doi(hep_submission.doi, 'http://www.hepdata.net/record/ins{0}'.format(publication_info['inspire_id']),
                 base_xml, publication_info['uuid'])

    register_doi(version_doi, 'http://www.hepdata.net/record/ins{0}?version={1}'.format(
        publication_info['inspire_id'], hep_submission.latest_version), version_xml, publication_info['uuid'])


@shared_task
def generate_doi_for_data_submission(data_submission_id, version):
    data_submission = DataSubmission.query.filter_by(id=data_submission_id).first()

    hep_submission = HEPSubmission.query.filter_by(publication_recid=data_submission.publication_recid).first()

    publication_info = get_record_by_id(data_submission.publication_recid)

    data_file = DataResource.query.filter_by(id=data_submission.data_file).first()

    license = None
    if data_file:
        if data_file.file_license:
            license = License.query.filter_by(id=data_file.file_license).first()

    xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                          doi=data_submission.doi,
                          table_name=decode_string(data_submission.name),
                          table_description=decode_string(data_submission.description),
                          overall_submission=hep_submission,
                          data_submission=data_submission,
                          license=license,
                          publication_info=publication_info)

    register_doi(data_submission.doi, 'http://www.hepdata.net/record/{0}?version={1}&table={2}'.format(
        hep_submission.publication_recid, data_submission.version, data_submission.name),
                 xml, publication_info['uuid'])


def reserve_doi_for_hepsubmission(hepsubmission):
    base_doi = "{0}/hepdata.{1}".format(
        current_app.config.get('DOI_PREFIX'), hepsubmission.publication_recid)

    version = hepsubmission.latest_version
    if version == 0:
        version += 1

    if hepsubmission.doi is None:
        create_doi(base_doi)
        hepsubmission.doi = base_doi
        db.session.add(hepsubmission)
        db.session.commit()

    create_doi(base_doi + ".v{0}".format(version))


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
        version = data_submission.version
        if version == 0:
            version += 1

        doi_value = "{0}/hepdata.{1}.v{2}/t{3}".format(
            current_app.config.get('DOI_PREFIX'), publication_recid, version, (index + 1))

        if data_submission.doi is None:
            create_doi(doi_value)
            data_submission.doi = doi_value
            db.session.add(data_submission)

    db.session.commit()


def create_doi(doi):
    """
    :param doi: Creates a DOI using the data provider. If it already exists, we return back the existing provider.
    :return: DataCiteProvider
    """
    try:
        return DataCiteProvider.create(doi)
    except Exception:
        return DataCiteProvider.get(doi, 'doi')


def register_doi(doi, url, xml, uuid):
    """
    Given a data submission id, this method takes it's assigned DOI, creates the DataCite XML,
    and registers the DOI.
    :param data_submissions:
    :param recid:
    :return:
    """

    print '{0} - {1}'.format(doi, url)

    try:
        provider = DataCiteProvider.get(doi, 'doi')
    except PIDDoesNotExistError:
        provider = create_doi(doi)

    pidstore_obj = PersistentIdentifier.query.filter_by(pid_value=doi).first()
    if pidstore_obj:
        pidstore_obj.object_uuid = uuid
        db.session.add(pidstore_obj)
    db.session.commit()

    try:
        provider.register(url, xml)
    except PIDInvalidAction, IntegrityError:
        provider.update(url, xml)
