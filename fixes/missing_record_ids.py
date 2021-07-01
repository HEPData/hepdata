from datetime import datetime

from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db

from hepdata.cli import fix
from hepdata.ext.elasticsearch.api import index_record_ids, push_data_keywords
from hepdata.modules.submission.models import HEPSubmission, DataSubmission
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.doi_minter import generate_doi_for_table
from hepdata.modules.records.utils.submission import finalise_datasubmission


@fix.command()
@with_appcontext
def create_missing_datasubmission_records():
    # Get submissions with missing IDs
    missing_submissions = DataSubmission.query \
        .join(HEPSubmission, HEPSubmission.publication_recid == DataSubmission.publication_recid) \
        .filter(
            DataSubmission.associated_recid == None,
            DataSubmission.publication_inspire_id == None,
            DataSubmission.version == HEPSubmission.version,
            HEPSubmission.overall_status == 'finished')
    missing_submissions = missing_submissions.all()

    if not missing_submissions:
        print("No datasubmissions found with missing record or inspire ids.")
        return

    # Organise missing submissions by publication
    submissions_by_publication = {}
    for submission in missing_submissions:
        if submission.publication_recid in submissions_by_publication:
            submissions_by_publication[submission.publication_recid].append(submission)
        else:
            submissions_by_publication[submission.publication_recid] = [submission]

    # Loop through each publication
    for publication_recid, submissions in submissions_by_publication.items():
        publication_record = get_record_by_id(publication_recid)
        current_time = "{:%Y-%m-%d %H:%M:%S}".format(datetime.utcnow())
        generated_record_ids = []
        for submission in submissions:
            # Finalise each data submission that does not have a record
            finalise_datasubmission(current_time, {},
                                    generated_record_ids,
                                    publication_record, publication_recid,
                                    submission,
                                    submission.version)

            # Register the datasubmission's DOI
            if not current_app.config.get('TESTING', False):
                generate_doi_for_table.delay(submission.doi)
                print(f"Generated DOI {submission.doi}")
            else:
                print(f"Would generate DOI {submission.doi}")

        # finalise_datasubmission does not commit, so commit once for each publication
        db.session.commit()

        # Reindex the publication and its updated datasubmissions
        index_record_ids([publication_recid] + generated_record_ids)
        push_data_keywords(pub_ids=[publication_recid])
