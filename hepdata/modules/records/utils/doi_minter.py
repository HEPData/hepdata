from celery import shared_task
from flask import render_template
from invenio_db import db

from invenio_pidstore.providers.datacite import DataCiteProvider

from hepdata.config import TEST_DOI_PREFIX
from hepdata.modules.records.models import DataSubmission, HEPSubmission
from hepdata.modules.records.utils.common import get_record_by_id


def reserve_dois_for_data_submissions(publication_recid):
    """
    Reserves a DOI for a data submission and saves to the datasubmission object.
    :param data_submission: DataSubmission object representing a data table.
    :return:
    """
    data_submissions = DataSubmission.query.filter_by(publication_recid=publication_recid).all()

    for data_submission in data_submissions:
        doi_value = "{0}/hepdata.{1}".format(TEST_DOI_PREFIX, data_submission.id)
        DataCiteProvider.create(doi_value)
        data_submission.doi = doi_value

        db.session.add(data_submission)
    db.session.commit()


@shared_task
def register_doi(data_submission_id):
    """
    Given a data submission id, this method takes it's assigned DOI, creates the DataCite XML,
    and registers the DOI.
    :param data_submissions:
    :param recid:
    :return:
    """
    data_submission = DataSubmission.query.filter_by(id=data_submission_id).first()

    if data_submission:
        hep_submission = HEPSubmission.query.filter_by(publication_recid=data_submission.publication_recid)
        provider = DataCiteProvider.get(data_submission.doi, 'doi')

        publication_info = get_record_by_id(data_submission.publication_recid)

        xml = render_template('hepdata_records/formats/datacite/datacite_complete.xml',
                              doi=data_submission.doi,
                              overall_submission=hep_submission,
                              data_submission=data_submission, licenses=[],
                              publication_info=publication_info)

        provider.register('http://www.hepdata.net/record/{0}'.format(data_submission.doi), xml)
    else:
        print('No DOI minted for Data Submission {0}'.format(data_submission_id))
