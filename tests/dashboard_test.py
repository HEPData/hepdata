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
from invenio_db import db
from hepdata.modules.dashboard.api import add_user_to_metadata, \
    create_record_for_dashboard, prepare_submissions, \
    get_pending_invitations_for_user, get_submission_count, \
    list_submission_titles
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from invenio_accounts.models import User, Role
from pytest_mock import mocker
from . import conftest
import pytest

dashboardTestMockObjects = {
    'user': User(email='test@test.com', password='hello1', active=True, id=101),
    'user2': User(email='test2@test.com', password='hello2', active=True, id=202)
}

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
        hepsubmission = get_or_create_hepsubmission(record_information['recid'])
        record = get_record_by_id(record_information['recid'])
        user = User(email='test@test.com', password='hello1', active=True,
                    id=101)

        test_submissions = {}
        create_record_for_dashboard(record['recid'], test_submissions, user)
        assert(test_submissions == {
            record_information['recid']: {
                'metadata': {
                    'coordinator': {'name': 'No coordinator'},
                    'recid': record_information['recid'],
                    'role': ['coordinator'],
                    'start_date': hepsubmission.created,
                    'last_updated': hepsubmission.last_updated,
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

        create_record_for_dashboard(record['recid'], test_submissions, user)
        assert(test_submissions == {
            record_information['recid']: {
                "metadata": {"role": [['coordinator']]}
            }
        })


def test_submissions_empty(app):
    with app.app_context():
        user = User(email='test@test.com', password='hello1', active=True, id=101)
        assert(get_submission_count(user) == 0)
        assert(list_submission_titles(user) == [])
        assert(prepare_submissions(user) == {})


def test_submissions_admin(app, load_submission):
    with app.app_context():
        record_information = create_record({
            'journal_info': 'Phys. Letts',
            'title': 'My Journal Paper',
            'inspire_id': '1487726'
        })
        hepsubmission = get_or_create_hepsubmission(record_information['recid'])

        role = Role(name='admin')
        user = User(email='test@test.com', password='hello1', active=True,
                    id=101, roles=[role])

        assert(get_submission_count(user) == 1)
        assert(list_submission_titles(user) == [{
            'id': record_information['recid'],
            'title': 'My Journal Paper'
        }])

        submissions = prepare_submissions(user)
        assert(len(submissions) == 1)
        assert(submissions[str(record_information['recid'])] == {
            'metadata': {
                'coordinator': {'email': u'test@hepdata.net',
                                'name': u'test@hepdata.net',
                                'id': 1},
                'recid': str(record_information['recid']),
                'role': ['coordinator'],
                'show_coord_view': False,
                'start_date': hepsubmission.created,
                'last_updated': hepsubmission.last_updated,
                'title': u'My Journal Paper',
                'versions': 1
            },
            'stats': {'attention': 0, 'passed': 0, 'todo': 0},
            'status': u'todo'
        })


def test_submissions_participant(app, load_submission):
    with app.app_context():
        record_information = create_record({
            'journal_info': 'Phys. Letts',
            'title': 'My Journal Paper',
            'inspire_id': '1487726'
        })
        hepsubmission = get_or_create_hepsubmission(record_information['recid'])

        user = User(email='test@test.com', password='hello1', active=True)
        db.session.add(user)
        db.session.commit()

        participant = SubmissionParticipant(
            publication_recid=record_information['recid'],
            role="uploader",
            email='test@test.com',
            status='primary',
            user_account=user.id)
        db.session.add(participant)
        hepsubmission.participants.append(participant)
        db.session.add(hepsubmission)
        db.session.commit()

        assert(get_submission_count(user) == 1)
        assert(list_submission_titles(user) == [{
            'id': record_information['recid'],
            'title': 'My Journal Paper'
        }])

        participant_submissions = prepare_submissions(user)
        assert(len(participant_submissions) == 1)
        assert(participant_submissions[str(record_information['recid'])] == {
            'metadata': {
                'coordinator': {'email': u'test@hepdata.net',
                                'name': u'test@hepdata.net',
                                'id': 1},
                'recid': str(record_information['recid']),
                'role': ['uploader'],
                'show_coord_view': False,
                'start_date': hepsubmission.created,
                'last_updated': hepsubmission.last_updated,
                'title': u'My Journal Paper',
                'versions': 1
            },
            'stats': {'attention': 0, 'passed': 0, 'todo': 0},
            'status': u'todo'
        })

        # Add a new submission as coordinator
        record_information2 = create_record({
            'journal_info': 'Another Journal',
            'title': 'My New Journal Paper',
            'inspire_id': '123456'
        })
        hepsubmission = get_or_create_hepsubmission(record_information2['recid'], coordinator=user.id)

        assert(get_submission_count(user) == 2)
        assert(list_submission_titles(user) == [
            {
                'id': record_information2['recid'],
                'title': 'My New Journal Paper'
            },
            {
                'id': record_information['recid'],
                'title': 'My Journal Paper'
            }
        ])

        all_submissions = prepare_submissions(user)
        assert(len(all_submissions) == 2)
        assert(all_submissions[str(record_information2['recid'])] == {
            'metadata': {
                'coordinator': {'email': u'test@test.com',
                                'name': u'test@test.com',
                                'id': user.id},
                'recid': str(record_information2['recid']),
                'role': ['coordinator'],
                'show_coord_view': True,
                'start_date': hepsubmission.created,
                'last_updated': hepsubmission.last_updated,
                'title': u'My New Journal Paper',
                'versions': 1
            },
            'stats': {'attention': 0, 'passed': 0, 'todo': 0},
            'status': u'todo'
        })

        # Check pagination
        page1_submissions = prepare_submissions(user, 1)
        assert(len(page1_submissions) == 1)
        assert(page1_submissions[str(record_information2['recid'])]
               == all_submissions[str(record_information2['recid'])])

        page2_submissions = prepare_submissions(user, 1, 2)
        assert(len(page2_submissions) == 1)
        assert(page2_submissions[str(record_information['recid'])]
               == all_submissions[str(record_information['recid'])])

        # Check filtering by record id
        record_submissions = prepare_submissions(user, record_id=record_information2['recid'])
        assert(len(record_submissions) == 1)
        assert(record_submissions[str(record_information2['recid'])]
               == all_submissions[str(record_information2['recid'])])

        # change status to 'finished' and check new submission no longer appears
        hepsubmission.overall_status = 'finished'
        db.session.add(hepsubmission)
        db.session.commit()

        assert(get_submission_count(user) == 1)
        all_submissions = prepare_submissions(user)
        assert(len(all_submissions) == 1)
        assert(list(all_submissions.keys()) == [str(record_information['recid'])])


def test_get_pending_invitations_for_user_empty(app):
    with app.app_context():
        user = dashboardTestMockObjects['user']
        pending = get_pending_invitations_for_user(user)
        assert(pending == [])

@pytest.fixture()
def mocked_submission_participant_app(request, mocker):
    global dashboardTestMockObjects

    # Create the flask app
    app = conftest.create_basic_app()

    # Create some mock objects and chain the mock calls
    def mock_all():
        return [
            mocker.MagicMock(publication_recid=1, invitation_cookie='c00kie1', role='TestRole1'),
            mocker.MagicMock(publication_recid=2, invitation_cookie='c00kie2', role='TestRole2')
        ]

    mockFilter = mocker.Mock(all=mock_all)
    mockQuery = mocker.Mock(filter=lambda a, b, c, d: mockFilter)
    mockSubmissionParticipant = mocker.Mock(query=mockQuery)

    # Patch some methods called from hepdata.modules.dashboard.api so they return mock values
    dashboardTestMockObjects['submission'] = \
        mocker.patch('hepdata.modules.dashboard.api.SubmissionParticipant',
                     mockSubmissionParticipant)
    mocker.patch('hepdata.modules.dashboard.api.get_record_by_id',
                 lambda x: {'title': 'Test Title 1' if x <= 1 else 'Test Title 2'})
    mocker.patch('hepdata.modules.dashboard.api.get_latest_hepsubmission',
                 mocker.Mock(coordinator=101))
    mocker.patch('hepdata.modules.dashboard.api.get_user_from_id',
                 mocker.Mock(return_value=dashboardTestMockObjects['user']))
    mocker.patch('hepdata.modules.dashboard.api.decode_string',
                 lambda x: "decoded " + str(x))

    # Do the rest of the app setup
    app_generator = conftest.setup_app(app)
    for app in app_generator:
        yield app


def test_get_pending_invitations_for_user(mocked_submission_participant_app, mocker):
    global dashboardTestMockObjects

    with mocked_submission_participant_app.app_context():
        user = dashboardTestMockObjects['user']
        pending = get_pending_invitations_for_user(user)

        expected = [{
            'coordinator': user,
            'invitation_cookie': 'c00kie1',
            'role': 'TestRole1',
            'title': 'decoded Test Title 1'
        }, {
            'coordinator': user,
            'invitation_cookie': 'c00kie2',
            'role': 'TestRole2',
            'title': 'decoded Test Title 2'
        }]
        assert(pending == expected)
