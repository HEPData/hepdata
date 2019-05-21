# -*- coding: utf-8 -*-
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

"""HEPData user queries."""
from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy import or_


def get_user_from_id(user_id):
    """
    Returns a user object from their id.

    :param user_id: <int>
    :return: User object if found, else None
    """
    user_query = db.session.query(User).filter(User.id == user_id)
    if user_query.count() > 0:
        return user_query.one()
    else:
        return None


def user_is_admin(user):
    """
    Checks if user is an admin or coordinator.

    :param user: <User> object
    """
    if user and user.is_authenticated:
        id = int(user.get_id())
        with db.session.no_autoflush:
            roles = User.query.filter(User.id == id).filter(
                    User.roles.any(name='admin')).all()
        return len(roles) > 0
    return False


def user_is_admin_or_coordinator(user):
    """
    Checks if user is an admin or coordinator.

    :param user: <User> object
    """
    if user and user.is_authenticated:
        id = int(user.get_id())
        with db.session.no_autoflush:
            roles = User.query.filter(User.id == id).filter(
                or_(User.roles.any(name='coordinator'),
                    User.roles.any(name='admin'))).all()

        return len(roles) > 0
    return False
