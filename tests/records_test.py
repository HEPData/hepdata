#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

"""HEPData records test cases."""
from invenio_accounts.models import User

from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_record, create_record
from tests.conftest import TEST_EMAIL


def test_record_creation(app):
    """___test_record_creation___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        assert(record_information['recid'])
        assert(record_information['uuid'])
        assert(record_information['title'] == 'My Journal Paper')


def test_record_update(app):
    """___test_record_update___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        record = get_record_by_id(record_information['recid'])
        print(record)
        assert (record['title'] == 'My Journal Paper')
        assert (record['journal_info'] == 'Phys. Letts')
        update_record(record_information['recid'], {'journal_info': 'test'})

        updated_record = get_record_by_id(record_information['recid'])
        assert (updated_record['journal_info'] == 'test')


def test_get_coordinators(app):
    with app.app_context():
        coordinators = get_coordinators_in_system()
        assert(len(coordinators) == 1)


def test_has_role(app):
    with app.app_context():
        user = User.query.filter_by(email=TEST_EMAIL).first()
        assert(user is not None)
        assert(has_role(user, 'coordinator'))
        assert(not has_role(user, 'awesome'))
