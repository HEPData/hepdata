import click
import logging

from celery import shared_task
from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db

from hepdata.celery import dynamic_tasks
from hepdata.config import SIMPLEANALYSIS_FILE_TYPE, HS3_FILE_TYPE
from hepdata.cli import fix
from hepdata.ext.opensearch.api import reindex_batch
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission
from hepdata.modules.records.utils.common import is_analysis

logging.basicConfig()
log = logging.getLogger(__name__)

@fix.command()
@with_appcontext
@click.option('--analyses-type', '-a', type=str, help=f"e.g. '{SIMPLEANALYSIS_FILE_TYPE}' or '{HS3_FILE_TYPE}'.")
@click.option('--batch-size', '-b', type=int, default=20,
              help='Number of hepsubmission entries to check at a time.')
@click.option('--synchronous', '-s', type=bool, default=False)
def add_analyses(analyses_type, batch_size, synchronous=False):
    """Check all submissions for resources with analyses_type in the description but not as the type."""

    if analyses_type not in (SIMPLEANALYSIS_FILE_TYPE, HS3_FILE_TYPE):
        log.error(f"analyses-type must be '{SIMPLEANALYSIS_FILE_TYPE}' or '{HS3_FILE_TYPE}'")
        return

    all_ids = db.session.query(HEPSubmission.id).order_by(HEPSubmission.id).all()

    count = 0
    total = len(all_ids)
    while count < total:
        batch_ids = [i[0] for i in all_ids[count:min(count + batch_size, total)]]
        if synchronous:
            _add_analyses_batch(analyses_type, batch_ids)
        else:
            log.info('Sending batch of IDs {0} to {1} to celery'.format(batch_ids[0], batch_ids[-1]))
            dynamic_tasks.delay('_add_analyses_batch', 'add_analyses', analyses_type, batch_ids)
        count += batch_size


@shared_task
def _add_analyses_batch(analyses_type, ids):
    log.info(f"Checking for {analyses_type} resources in submission ids {ids}")
    recids_to_reindex = []
    for id in ids:
        hepsubmission = HEPSubmission.query.get(id)

        if hepsubmission:
            for resource in hepsubmission.resources:
                if resource.file_type != analyses_type and is_analysis(analyses_type, resource.file_description):
                    log.info(f"Found {analyses_type} for resource {resource.file_location}")
                    # Update resource to have type analyses_type
                    resource.file_type = analyses_type
                    db.session.add(resource)
                    db.session.commit()

                    # Check if this is the latest finished submission - reindex if so
                    latest_submission = get_latest_hepsubmission(publication_recid=hepsubmission.publication_recid, overall_status='finished')
                    if latest_submission and latest_submission.version == hepsubmission.version:
                        recids_to_reindex.append(hepsubmission.id)

    if recids_to_reindex:
        recids_to_reindex = list(set(recids_to_reindex))  # remove duplicates before indexing
        log.info(f"Reindexing records: {recids_to_reindex}")
        reindex_batch(recids_to_reindex, current_app.config['OPENSEARCH_INDEX'])
