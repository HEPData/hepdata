import click
import logging

from celery import shared_task
from flask.cli import with_appcontext
from invenio_db import db
from invenio_search import RecordsSearch
from sqlalchemy import and_, distinct
from sqlalchemy.orm import aliased

from hepdata.cli import fix
from hepdata.ext.elasticsearch.api import default_index
from hepdata.modules.submission.models import HEPSubmission, DataSubmission

logging.basicConfig()
log = logging.getLogger(__name__)


@fix.command()
@with_appcontext
@click.option('--batch', '-b', type=int, default=5,
              help='Number of hepsubmission entries to cleanup at a time.')
def cleanup_index(batch):
    """Clean up old datasubmission entries from elasticsearch"""
    cleanup_index_all(batch=batch)


@default_index
def cleanup_index_all(index=None, batch=5, synchronous=False):
    # Find entries in elasticsearch which are from previous versions of submissions and remove
    # Get all finished HEPSubmission ids with version numbers less than the max
    # finished version by doing a left outer join of hepsubmission with itself
    h1 = aliased(HEPSubmission)
    h2 = aliased(HEPSubmission)

    qry = db.session.query(distinct(h1.id)) \
        .join(h2,
              and_(h1.publication_recid == h2.publication_recid,
                   h1.version < h2.version,
                   h2.overall_status == 'finished'),
              isouter=True) \
        .filter(h2.id != None) \
        .order_by(h1.id)
    res = qry.all()
    ids = [x[0] for x in res]

    count = 0
    while count < len(ids):
        batch_ids = ids[count:min(count + batch, len(ids))]
        if synchronous:
            cleanup_index_batch(batch_ids, index)
        else:
            print('Sending batch of IDs {0} to {1} to celery'.format(batch_ids[0], batch_ids[-1]))
            cleanup_index_batch.delay(batch_ids, index)
        count += batch


@shared_task
def cleanup_index_batch(hepsubmission_record_ids, index):
    log.info('Cleaning up index for data records for hepsubmission IDs {0} to {1}'.format(hepsubmission_record_ids[0], hepsubmission_record_ids[-1]))
    # Find all datasubmission entries matching the given hepsubmission ids,
    # where the version is not the highest version present (i.e. there is not
    # a v2 record with the same associated_recid)
    d1 = aliased(DataSubmission)
    d2 = aliased(DataSubmission)
    qry = db.session.query(d1.associated_recid) \
        .join(HEPSubmission,
              and_(HEPSubmission.publication_recid == d1.publication_recid,
                   HEPSubmission.version == d1.version),
              isouter=True) \
        .join(d2,
              and_(d1.associated_recid == d2.associated_recid,
                   d1.version < d2.version),
              isouter=True) \
        .filter(HEPSubmission.id.in_(hepsubmission_record_ids), d2.id == None) \
        .order_by(d1.id)
    res = qry.all()

    ids = [x[0] for x in res]
    if ids:
        log.info(f'Deleting entries from index with ids {ids}')
        s = RecordsSearch(index=index).filter('terms', _id=ids)
        s.delete()
