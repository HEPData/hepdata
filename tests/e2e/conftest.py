# -*- coding: utf-8 -*-
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

"""PyTest Config"""

from __future__ import absolute_import, print_function

import multiprocessing
import os
import shutil
import tempfile
import time

import pytest
from invenio_accounts.models import User, Role
from invenio_db import db
from selenium import webdriver
from sqlalchemy_utils.functions import create_database, database_exists, \
    drop_database

from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.factory import create_app
from hepdata.modules.records.migrator.api import load_files
from tests.conftest import identifiers


@pytest.fixture()
def app(request):
    """Flask application fixture for E2E/integration/selenium tests.
    Overrides the `app` fixture found in `../conftest.py`. Tests/files in this
    folder and subfolders will see this variant of the `app` fixture.
    """
    app = create_app()
    app.config.update(dict(
        TESTING=True,
        TEST_RUNNER="celery.contrib.test_runner.CeleryTestSuiteRunner",
        CELERY_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        MAIL_SUPPRESS_SEND=True,
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg2://localhost/hepdata_test')
    ))

    with app.app_context():
        if not database_exists(str(db.engine.url)):
            create_database(str(db.engine.url))
        db.create_all()

    with app.app_context():
        db.drop_all()
        db.create_all()
        reindex_all(recreate=True)

        ctx = app.test_request_context()
        ctx.push()

        user_count = User.query.filter_by(email='test@hepdata.net').count()
        if user_count == 0:
            user = User(email='test@hepdata.net', password='hello1', active=True)
            admin_role = Role(name='admin')
            coordinator_role = Role(name='coordinator')

            user.roles.append(admin_role)
            user.roles.append(coordinator_role)

            db.session.add(admin_role)
            db.session.add(coordinator_role)
            db.session.add(user)
            db.session.commit()

        load_default_data(app)

    def teardown():
        with app.app_context():
            db.drop_all()
            ctx.pop()

    request.addfinalizer(teardown)

    return app


@pytest.fixture()
def load_default_data(app):
    with app.app_context():
        to_load = [x["hepdata_id"] for x in identifiers()]
        load_files(to_load, synchronous=True)


def pytest_generate_tests(metafunc):
    """Override pytest's default test collection function.
    For each test in this directory which uses the `env_browser` fixture, said
    test is called once for each value found in the `E2E_WEBDRIVER_BROWSERS`
    environment variable.
    """
    browsers = ['Firefox']

    if 'env_browser' in metafunc.fixturenames:
        # In Python 2.7 the fallback kwarg of os.environ.get is `failobj`,
        # in 3.x it's `default`.
        metafunc.parametrize('env_browser', browsers, indirect=True)


@pytest.fixture()
def env_browser(request):
    """Create a webdriver instance of the browser specified by request.
    The default browser is Firefox.  The webdriver instance is killed after the
    number of seconds specified by the ``E2E_WEBDRIVER_TIMEOUT`` variable or
    defaults to 300 (five minutes).
    """
    timeout = int(os.environ.get('E2E_WEBDRIVER_TIMEOUT', 300))

    def wait_kill():
        time.sleep(timeout)
        browser.quit()

    def finalizer():
        browser.quit()
        timeout_process.terminate()

    timeout_process = multiprocessing.Process(target=wait_kill)

    # Create instance of webdriver.`request.param`()
    print(request.param)

    browser = getattr(webdriver, request.param)()
    # Add finalizer to quit the webdriver instance
    request.addfinalizer(finalizer)

    timeout_process.start()
    return browser
