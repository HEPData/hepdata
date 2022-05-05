import click
import logging

from celery import shared_task
from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db

from hepdata.celery import dynamic_tasks
from hepdata.config import HISTFACTORY_FILE_TYPE
from hepdata.cli import fix
from hepdata.ext.elasticsearch.api import reindex_batch
from hepdata.modules.records.utils.common import is_histfactory
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission
from hepdata.modules.records.utils.doi_minter import create_resource_doi

logging.basicConfig()
log = logging.getLogger(__name__)

@fix.command()
@with_appcontext
@click.option('--batch-size', '-b', type=int, default=20,
              help='Number of hepsubmission entries to check at a time.')
@click.option('--synchronous', '-s', type=bool, default=False)
def add_histfactory_analyses(batch_size, synchronous=False):
    all_ids = db.session.query(HEPSubmission.id).order_by(HEPSubmission.id).all()

    count = 0
    total = len(all_ids)
    while count < total:
        batch_ids = [i[0] for i in all_ids[count:min(count + batch_size, total)]]
        if synchronous:
            _add_histfactory_analyses_batch(batch_ids)
        else:
            log.info('Sending batch of IDs {0} to {1} to celery'.format(batch_ids[0], batch_ids[-1]))
            dynamic_tasks.delay('_add_histfactory_analyses_batch', 'add_histfactory_analyses', batch_ids)
        count += batch_size


@shared_task
def _add_histfactory_analyses_batch(ids):
    log.info(f"Checking for HistFactory resources in submission ids {ids}")
    recids_to_reindex = []
    for id in ids:
        hepsubmission = HEPSubmission.query.get(id)

        if hepsubmission:
            for resource in hepsubmission.resources:
                if resource.file_type != HISTFACTORY_FILE_TYPE and \
                    is_histfactory(resource.file_location, resource.file_description):
                        log.info(f"Found histfactory for resource {resource.file_location}")
                        # Update resource to have type histfactory
                        resource.file_type = HISTFACTORY_FILE_TYPE
                        db.session.add(resource)
                        db.session.commit()

                        # Check if this is the latest finished submission - reindex if so
                        latest_submission = get_latest_hepsubmission(publication_recid=hepsubmission.publication_recid, overall_status='finished')
                        if latest_submission and latest_submission.version == hepsubmission.version:
                            recids_to_reindex.append(hepsubmission.id)

                        if hepsubmission.overall_status == 'finished':
                            site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
                            create_resource_doi.delay(hepsubmission.id, resource.id, site_url)

    if recids_to_reindex:
        log.info(f"Reindexing records: {recids_to_reindex}")
        reindex_batch(recids_to_reindex, current_app.config['ELASTICSEARCH_INDEX'])
