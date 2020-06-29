#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""HEPData Subscribers API."""
from functools import partial
from operator import is_not

from flask_login import current_user

from hepdata.modules.records.utils.common import get_record_contents
from .models import Subscribers


def is_current_user_subscribed_to_record(recid):
    if not current_user.is_authenticated:
        return False

    return Subscribers.query.filter(Subscribers.publication_recid == recid,
                                    Subscribers.subscribers.contains(current_user)).count() > 0


def get_users_subscribed_to_record(recid):
    subscribers = Subscribers.query.filter_by(publication_recid=recid).first()

    if subscribers:
        return [{'email': x.email, 'id': x.id} for x in subscribers.subscribers]
    else:
        return []


def get_records_subscribed_by_current_user():
    subscriptions = Subscribers.query.filter(Subscribers.subscribers.contains(current_user)).all()
    if subscriptions:
        records = [get_record_contents(x.publication_recid) for x in subscriptions]
        return list(filter(partial(is_not, None), records))

    else:
        return []
