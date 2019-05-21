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
from invenio_accounts.models import User


def get_coordinators_in_system():
    """
    Utility function to get all coordinator users in the database.

    :return: list of coordinator ids, nicknames, and emails.
    """

    coordinators = User.query.filter(User.roles.any(name='coordinator')).all()

    to_return = [{'id': coordinator.id, 'nickname': coordinator.email,
                  'email': coordinator.email} for coordinator in coordinators]

    return to_return


def has_role(user, required_role):
    """
    Determines if a user has a particular role.

    :param user: a current_user object
    :param required_role: e.g. 'admin'
    :return: True if the user has the role, False otherwise
    """
    for role in user.roles:
        if role.name == required_role:
            return True
    return False
