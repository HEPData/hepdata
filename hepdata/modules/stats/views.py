from datetime import datetime
from invenio_db import db
from sqlalchemy import func

from hepdata.modules.stats.models import DailyAccessStatistic

__author__ = 'eamonnmaguire'


def get_date():
    return datetime.today()


def increment(recid):
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
    try:
        result = DailyAccessStatistic.query.with_entities(
            func.sum(DailyAccessStatistic.count).label('sum')).filter(
            DailyAccessStatistic.publication_recid == recid).one()
        return {"sum": int(result.sum)}

    except Exception as e:
        print e
        return {"sum": 1}
