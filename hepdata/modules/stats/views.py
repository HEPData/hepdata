import logging
from datetime import datetime
from invenio_db import db
from sqlalchemy import func

from hepdata.modules.stats.models import DailyAccessStatistic

__author__ = 'eamonnmaguire'

logging.basicConfig()
log = logging.getLogger(__name__)


def get_date():
    """
    Gets todays' date
    :return: datetime object
    """
    return datetime.today()


def increment(recid):
    """
    Increases the number of accesses to the record
    by 1
    :param recid: id of the record accessed
    :return:
    """
    if recid:
        dt = get_date()
        try:
            available_access_stats = DailyAccessStatistic.query.filter_by(
                publication_recid=recid, day=dt.strftime('%Y-%m-%d')).first()

            if available_access_stats:
                available_access_stats.count += 1
            else:
                stats = DailyAccessStatistic(
                    publication_recid=recid, day=dt, count=1)
                db.session.add(stats)
            db.session.commit()
        except:
            db.session.rollback()


def get_count(recid):
    """
    Returns the number of times the record has been accessed
    :param recid: record id to get the count for
    :return: dict with sum as a key {"sum": 2}
    """
    if recid:
        try:
            result = DailyAccessStatistic.query.with_entities(
                func.sum(DailyAccessStatistic.count).label('sum')).filter(
                DailyAccessStatistic.publication_recid == recid).one()
            return {"sum": int(result.sum)}

        except Exception as e:
            log.error(e)
            return {"sum": 1}
