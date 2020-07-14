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
from io import open, StringIO
import os
import yaml
import datetime

from flask_login import login_user
from invenio_accounts.models import User
from invenio_db import db
from werkzeug.datastructures import FileStorage

from hepdata.modules.records.api import process_payload
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.data_processing_utils import generate_table_structure
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_record, create_record
from hepdata.modules.submission.models import HEPSubmission
from tests.conftest import TEST_EMAIL
from hepdata.modules.records.utils.records_update_utils import get_all_updated_records_since_date, update_record_info


def test_record_creation(app):
    """___test_record_creation___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        assert (record_information['recid'])
        assert (record_information['uuid'])
        assert (record_information['title'] == 'My Journal Paper')


def test_record_update(app):
    """___test_record_update___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        record = get_record_by_id(record_information['recid'])
        assert (record['title'] == 'My Journal Paper')
        assert (record['journal_info'] == 'Phys. Letts')
        update_record(record_information['recid'], {'journal_info': 'test'})

        updated_record = get_record_by_id(record_information['recid'])
        assert (updated_record['journal_info'] == 'test')


def test_get_record(app, client):
    with app.app_context():
        content = client.get('/record/1')
        assert (content is not None)


def test_get_coordinators(app):
    with app.app_context():
        coordinators = get_coordinators_in_system()
        assert (len(coordinators) == 1)


def test_has_role(app):
    with app.app_context():
        user = User.query.filter_by(email=TEST_EMAIL).first()
        assert (user is not None)
        assert (has_role(user, 'coordinator'))
        assert (not has_role(user, 'awesome'))


def test_data_processing(app):
    base_dir = os.path.dirname(os.path.realpath(__file__))

    data = yaml.safe_load(open(os.path.join(base_dir, 'test_data/data_table.yaml'), 'rt'))

    assert ('independent_variables' in data)
    assert ('dependent_variables' in data)

    assert (len(data['independent_variables']) == 1)
    assert (len(data['independent_variables'][0]['values']) == 3)

    assert (len(data['dependent_variables']) == 1)
    assert (len(data['dependent_variables'][0]['values']) == 3)

    data["name"] = 'test'
    data["title"] = 'test'
    data["keywords"] = None
    data["doi"] = 'doi/10.2342'
    data["location"] = 'Data from Figure 2 of preprint'
    data["review"] = []
    data["associated_files"] = []

    table_structure = generate_table_structure(data)

    assert(table_structure["x_count"] == 1)
    assert(len(table_structure["headers"]) == 2)
    assert(len(table_structure["qualifiers"]) == 2)


def test_upload_valid_file(app):
    # Test uploading and processing a file for a record
    with app.app_context():
        base_dir = os.path.dirname(os.path.realpath(__file__))
        user = User.query.first()
        login_user(user)

        recid = '12345'
        get_or_create_hepsubmission(recid, 1)

        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission is not None)
        assert(hepdata_submission.data_abstract is None)
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        with open(os.path.join(base_dir, 'test_data/TestHEPSubmission.zip'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="TestHEPSubmission.zip"
            )
            response = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(response.json == {'url': '/test_redirect_url'})

        # Check the submission has been updated
        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission.data_abstract.startswith('CERN-LHC.  Measurements of the cross section  for ZZ production'))
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        # Set the status to finished and try again, to check versioning
        hepdata_submission.overall_status = 'finished'
        db.session.add(hepdata_submission)

        # Refresh user
        user = User.query.first()
        login_user(user)

        with open(os.path.join(base_dir, 'test_data/TestHEPSubmission.zip'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="TestHEPSubmission.zip"
            )
            process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        # Check the submission has been updated
        hepdata_submissions = HEPSubmission.query.filter_by(
            publication_recid=recid).order_by(HEPSubmission.last_updated).all()
        assert(len(hepdata_submissions) == 2)
        assert(hepdata_submissions[0].version == 1)
        assert(hepdata_submissions[0].overall_status == 'finished')
        assert(hepdata_submissions[1].data_abstract.startswith('CERN-LHC.  Measurements of the cross section  for ZZ production'))
        assert(hepdata_submissions[1].version == 2)
        assert(hepdata_submissions[1].overall_status == 'todo')


def test_upload_valid_file_yaml_gz(app):
    # Test uploading and processing a file for a record
    with app.app_context():
        base_dir = os.path.dirname(os.path.realpath(__file__))
        user = User.query.first()
        login_user(user)

        recid = '1512299'
        get_or_create_hepsubmission(recid, 1)

        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission is not None)
        assert(hepdata_submission.data_abstract is None)
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        with open(os.path.join(base_dir, 'test_data/1512299.yaml.gz'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="1512299.yaml.gz"
            )
            response = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(response.json == {'url': '/test_redirect_url'})

        # Check the submission has been updated
        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission.data_abstract.startswith('Unfolded differential decay rates of four kinematic variables'))
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        # Set the status to finished and try again, to check versioning
        hepdata_submission.overall_status = 'finished'
        db.session.add(hepdata_submission)

        # Refresh user
        user = User.query.first()
        login_user(user)

        with open(os.path.join(base_dir, 'test_data/1512299.yaml.gz'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="1512299.yaml.gz"
            )
            process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        # Check the submission has been updated
        hepdata_submissions = HEPSubmission.query.filter_by(
            publication_recid=recid).order_by(HEPSubmission.last_updated).all()
        assert(len(hepdata_submissions) == 2)
        assert(hepdata_submissions[0].version == 1)
        assert(hepdata_submissions[0].overall_status == 'finished')
        assert(hepdata_submissions[1].data_abstract.startswith('Unfolded differential decay rates of four kinematic variables'))
        assert(hepdata_submissions[1].version == 2)
        assert(hepdata_submissions[1].overall_status == 'todo')


def test_upload_invalid_file(app):
    # Test uploading an invalid file
    with app.app_context():
        user = User.query.first()
        login_user(user)

        recid = '12345'
        get_or_create_hepsubmission(recid, 1)

        with StringIO("test") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="test.txt"
            )
            response, code = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(code == 400)
        assert(response.json == {
            'message': 'You must upload a .zip, .tar, .tar.gz or .tgz file'
            ' (or a .oldhepdata or single .yaml or .yaml.gz file).'
        })


def test_get_updated_records_on_date(app):
    d0 = datetime.date.today()
    d1 = datetime.date(2020, 6, 29)
    delta = d0 - d1
    set(get_all_updated_records_since_date(delta.days, verbose=True))  # at the moment this is just a check that no exception is thrown
    # the following is broken by the 1 digit limitation in delta.days parameter (due to url call to inspire)
    # assert(set(get_all_updated_records_since_date(delta.days, verbose=True)) == set(['1650066', '1650063', '756925']))


def test_update_record_info(app):
    # dummy test: the record doesn't exist on Travis, so it's basically checking it can handle not-found record case
    assert(update_record_info("1311487") is None)
