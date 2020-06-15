#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#
"""HEPData Stats Views."""

import logging
from datetime import datetime
from invenio_db import db
from sqlalchemy import func

from hepdata.modules.stats.models import DailyAccessStatistic

logging.basicConfig()
log = logging.getLogger(__name__)


def get_date():
    """
    Gets today's date.

    :return: datetime object
    """
    return datetime.utcnow()


def increment(recid):
    """
    Increases the number of accesses to the record
    by 1.

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
    Returns the number of times the record has been accessed.

    :param recid: record id to get the count for
    :return: dict with sum as a key {"sum": 2}
    """
    if recid is not None:
        try:
            result = DailyAccessStatistic.query.with_entities(
                func.sum(DailyAccessStatistic.count).label('sum')).filter(
                DailyAccessStatistic.publication_recid == recid).one()
            return {"sum": int(result[0])}

        except Exception as e:
            log.info('No stats record found for {0}. Returning one.'.format(recid))
            log.info(e)

    return {"sum": 1}
