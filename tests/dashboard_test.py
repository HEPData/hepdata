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
from hepdata.modules.dashboard.api import add_user_to_metadata, \
    create_record_for_dashboard
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record

def test_add_user_to_metadata():
    test_submissions = {
        '123456': {
            "metadata": {"test_type": {}}
        }
    }
    test_info = {'full_name': 'test_name', 'email': 'test@test.com'}

    add_user_to_metadata('test_type', test_info, '123456', test_submissions)
    assert(test_submissions == {
        '123456': {
            "metadata": {
                'test_type': {
                    'name': 'test_name',
                    'email': 'test@test.com'
                }
            }
        }
    })

    test_submissions = {
        '123456': {
            "metadata": {"test_type": {}}
        }
    }
    add_user_to_metadata('test_type', None, '123456', test_submissions)
    assert(test_submissions == {
        '123456': {
            "metadata": {
                'test_type': {
                    'name': 'No primary test_type'
                }
            }
        }
    })


def test_create_record_for_dashboard(app):
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper', 'inspire_id': '1487726'})
        get_or_create_hepsubmission(record_information['recid'])
        record = get_record_by_id(record_information['recid'])

        test_submissions = {}
        create_record_for_dashboard(record['recid'], test_submissions)
        assert(test_submissions == {
            record_information['recid']: {
                'metadata': {
                    'coordinator': {'name': 'No coordinator'},
                    'recid': record_information['recid'],
                    'role': ['coordinator'],
                    'start_date': record.created,
                    'title': u'My Journal Paper',
                    'versions': 1
                },
                'stats': {'attention': 0, 'passed': 0, 'todo': 0},
                'status': 'todo'
            }
        })

        test_submissions = {
            record_information['recid']: {
                "metadata": {"role": []}
            }
        }

        create_record_for_dashboard(record['recid'], test_submissions)
        assert(test_submissions == {
            record_information['recid']: {
                "metadata": {"role": [['coordinator']]}
            }
        })
