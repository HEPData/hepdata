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

"""HEPData Test Fixtures"""

import os
import shutil
import time
from unittest import mock

from invenio_accounts.models import Role, User
from invenio_db import db
import pytest

from hepdata.ext.opensearch.admin_view.api import AdminIndexer
from hepdata.ext.opensearch.api import reindex_all
from hepdata.factory import create_app
from hepdata.modules.dashboard.api import create_record_for_dashboard
from hepdata.modules.records.importer.api import import_records, _download_file
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission, process_submission_directory
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.views import process_submission_payload

TEST_EMAIL = 'test@hepdata.net'
TEST_PWD = 'hello1'


def create_basic_app():
    app = create_app()
    test_db_host = app.config.get('TEST_DB_HOST', 'localhost')
    app.config.update(dict(
        TESTING=True,
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        MAIL_SUPPRESS_SEND=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        OPENSEARCH_INDEX="hepdata-main-test",
        SUBMISSION_INDEX='hepdata-submission-test',
        AUTHOR_INDEX='hepdata-authors-test',
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg2://hepdata:hepdata@' + test_db_host + '/hepdata_test')
    ))
    return app


def setup_app(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        reindex_all(recreate=True, synchronous=True)

        ctx = app.test_request_context()
        ctx.push()

        user_count = User.query.filter_by(email='test@hepdata.net').count()
        if user_count == 0:
            user = User(email=TEST_EMAIL, password='hello1', active=True)
            admin_role = Role(name='admin')
            coordinator_role = Role(name='coordinator')

            user.roles.append(admin_role)
            user.roles.append(coordinator_role)

            db.session.add(admin_role)
            db.session.add(coordinator_role)
            db.session.add(user)
            db.session.commit()

        yield app
        ctx.pop()


@pytest.fixture()
def app(request):
    """Flask app fixture."""
    app = create_basic_app()
    app_generator = setup_app(app)
    for app in app_generator:
        yield app


@pytest.fixture()
def admin_idx(app):
    with app.app_context():
        admin_idx = AdminIndexer()
        return admin_idx


@pytest.fixture()
def load_default_data(app, identifiers):
    import_default_data(app, identifiers)


def import_default_data(app, identifiers):
    with app.app_context():
        # Mock out the _download_file method in importer to avoid downloading the
        # sample files multiple times during testing
        def _test_download_file(base_url, inspire_id):
            filename = 'HEPData-ins{0}-v1.zip'.format(inspire_id)
            print(f'Looking for file {filename} in {app.config["CFG_TMPDIR"]}')
            expected_file_name = os.path.join(app.config["CFG_TMPDIR"], filename)
            if os.path.exists(expected_file_name):
                print("Using existing file at %s" % expected_file_name)
                return expected_file_name
            else:
                print("Reverting to normal _download_file method")
                return _download_file(base_url, inspire_id)

        with mock.patch('hepdata.modules.records.importer.api._download_file', wraps=_test_download_file):
            to_load = [x["hepdata_id"] for x in identifiers]
            import_records(to_load, synchronous=True)


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture()
def identifiers():
    return get_identifiers()

def get_identifiers():
    return [{"hepdata_id": "ins1283842", "inspire_id": '1283842',
             "title": "Measurement of the forward-backward asymmetry "
                      "in the distribution of leptons in $t\\bar{t}$ "
                      "events in the lepton+jets channel",
             "data_tables": 14,
             "arxiv": "arXiv:1403.1294"},

            {"hepdata_id": "ins1245023", "inspire_id": '1245023',
             "title": "High-statistics study of $K^0_S$ pair production in two-photon collisions",
             "data_tables": 40,
             "arxiv": "arXiv:1307.7457"},
            {"hepdata_id": "ins2751932", "inspire_id": '2751932',
             "title": "Search for pair production of higgsinos in events with two Higgs bosons and missing "
                      "transverse momentum in $\\sqrt{s}=13$ TeV $pp$ collisions at the ATLAS experiment",
             "data_tables": 66,
             "arxiv": "arXiv:2401.14922"}
            ]

@pytest.fixture()
def load_submission(app, load_default_data):
    import_records(['ins1487726'], synchronous=True)


def create_blank_test_record():
    """
    Helper function to create a single, blank, finished submission
    :returns submission: The newly created submission object
    """
    record_information = create_record(
        {'journal_info': 'Journal', 'title': 'Test Paper'})
    recid = record_information['recid']
    submission = get_or_create_hepsubmission(recid)
    # Set overall status to finished so related data appears on dashboard
    submission.overall_status = 'finished'
    user = User(email=f'test@test.com', password='hello1', active=True,
                id=1)
    test_submissions = {}
    create_record_for_dashboard(recid, test_submissions, user)
    return submission


def create_test_record(file_location, overall_status='finished'):
    """
    Helper function to create a dummy record with data.
    :param file_location: Path to the data directory.
    :param overall_status: Allows setting of custom overall status. Defaults to 'finished'.
    :returns test_submission: The newly created submission object
    """
    record = {'title': 'HEPData Testing',
                  'reviewer': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'uploader': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'message': 'This is ready',
                  'user_id': 1}
    # Set up a new test submission
    test_submission = process_submission_payload(**record)
    # Ensure the status is set to `finished` so the related data can be accessed.
    test_submission.overall_status = overall_status
    record_dir = get_data_path_for_record(test_submission.publication_recid, str(int(round(time.time()))))
    shutil.copytree(file_location, record_dir)
    process_submission_directory(record_dir, os.path.join(record_dir, 'submission.yaml'),
                                 test_submission.publication_recid)
    return test_submission
