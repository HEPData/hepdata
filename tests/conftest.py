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

from invenio_accounts.models import Role, User
from invenio_db import db
import pytest

from hepdata.ext.elasticsearch.admin_view.api import AdminIndexer
from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.factory import create_app
from hepdata.modules.records.migrator.api import Migrator, load_files

TEST_EMAIL = 'test@hepdata.net'
TEST_PWD = 'hello1'


def create_basic_app():
    app = create_app()
    test_db_host = app.config.get('TEST_DB_HOST', 'localhost')
    app.config.update(dict(
        TESTING=True,
        TEST_RUNNER="celery.contrib.test_runner.CeleryTestSuiteRunner",
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        MAIL_SUPPRESS_SEND=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        ELASTICSEARCH_INDEX="hepdata-main-test",
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
    with app.app_context():
        to_load = [x["hepdata_id"] for x in identifiers]
        load_files(to_load, synchronous=True)


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture()
def migrator():
    return Migrator()


@pytest.fixture()
def identifiers():
    return get_identifiers()

def get_identifiers():
    return [{"hepdata_id": "ins1283842", "inspire_id": 1283842,
             "title": "Measurement of the forward-backward asymmetry "
                      "in the distribution of leptons in $t\\bar{t}$ "
                      "events in the lepton$+$jets channel",
             "data_tables": 14,
             "arxiv": "arXiv:1403.1294"},

            {"hepdata_id": "ins1245023", "inspire_id": 1245023,
             "title": "High-statistics study of $K^0_S$ pair production in two-photon collisions",
             "data_tables": 40,
             "arxiv": "arXiv:1307.7457"}
            ]

@pytest.fixture()
def load_submission(app, load_default_data, migrator):
    migrator.load_file('ins1487726')
