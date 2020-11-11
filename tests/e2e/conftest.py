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

from builtins import str
import multiprocessing
import os
import shutil
import tempfile
import time
from datetime import datetime

import flask
import pytest
from invenio_accounts.models import User, Role
from invenio_db import db
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy_utils.functions import create_database, database_exists, \
    drop_database
from time import sleep

from hepdata.config import CFG_TMPDIR, RUN_SELENIUM_LOCALLY
from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.factory import create_app
from hepdata.modules.records.migrator.api import load_files
from tests.conftest import get_identifiers


@pytest.fixture(scope='session')
def app(request):
    """Flask application fixture for E2E/integration/selenium tests.
    Overrides the `app` fixture found in `../conftest.py`. Tests/files in this
    folder and subfolders will see this variant of the `app` fixture.
    """
    app = create_app()
    test_db_host = app.config.get('TEST_DB_HOST', 'localhost')
    # Note that in GitHub Actions we add "TESTING=True" and
    # "APP_ENABLE_SECURE_HEADERS=False" to config_local.py as well,
    # to ensure that they're set before the app is initialised,
    # as changing them later doesn't have the desired effect.
    app.config.update(dict(
        TESTING=True,
        TEST_RUNNER="celery.contrib.test_runner.CeleryTestSuiteRunner",
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        CELERY_TASK_EAGER_PROPAGATES=True,
        ELASTICSEARCH_INDEX="hepdata-main-test",
        SUBMISSION_INDEX='hepdata-submission-test',
        AUTHOR_INDEX='hepdata-authors-test',
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg2://hepdata:hepdata@' + test_db_host + '/hepdata_test'),
        APP_ENABLE_SECURE_HEADERS=False
    ))

    with app.app_context():
        if not database_exists(str(db.engine.url)):
            create_database(str(db.engine.url))
        db.create_all()

    with app.app_context():
        db.drop_all()
        db.create_all()
        reindex_all(recreate=True, synchronous=True)

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
            db.engine.dispose()
            db.drop_all()
            ctx.pop()

    request.addfinalizer(teardown)

    return app


@pytest.fixture()
def test_identifiers(app):
    return get_identifiers()


@pytest.fixture()
def search_tests(app):
    return [{"search_term": "collisions", "exp_collab_facet": "BELLE", "exp_hepdata_id": "ins1245023"},
            {"search_term": "leptons", "exp_collab_facet": "D0", "exp_hepdata_id": "ins1283842"}]


def load_default_data(app):
    with app.app_context():
        to_load = [x["hepdata_id"] for x in get_identifiers()]
        load_files(to_load, synchronous=True)


def pytest_generate_tests(metafunc):
    """Override pytest's default test collection function.
    For each test in this directory which uses the `env_browser` fixture, said
    test is called once for each value found in the `E2E_WEBDRIVER_BROWSERS`
    environment variable.
    """
    browsers = ['Chrome']

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

    sauce_username = os.environ.get('SAUCE_USERNAME', '')
    sauce_access_key = os.environ.get('SAUCE_ACCESS_KEY', '')
    remote_url = \
        "https://%s:%s@ondemand.eu-central-1.saucelabs.com:443/wd/hub" \
        % (sauce_username, sauce_access_key)

    # the desired_capabilities parameter tells us which browsers and OS to spin up.
    desired_cap = {
        'platform': 'Windows',
        'browserName': 'chrome',
        'build': os.environ.get('GITHUB_RUN_ID',
                                datetime.utcnow().strftime("%Y-%m-%d %H:00ish")),
        'name': request.node.name,
        'username': sauce_username,
        'accessKey': sauce_access_key,
        'tunnelIdentifier': os.environ.get('GITHUB_RUN_ID', '')
    }

    if not RUN_SELENIUM_LOCALLY:
        # This creates a webdriver object to send to Sauce Labs including the desired capabilities
        browser = webdriver.Remote(remote_url, desired_capabilities=desired_cap)
    else:
        # Run tests locally instead of on Sauce Labs (requires local chromedriver installation).
        browser = getattr(webdriver, request.param)()

    browser.set_window_size(1004,632)

    # Go to homepage and click cookie accept button so cookie bar is out of the way
    browser.get(flask.url_for('hepdata_theme.index', _external=True))
    wait = WebDriverWait(browser, 10)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cc_btn_accept_all")))
    sleep(1)
    cookie_accept_btn = browser.find_element_by_css_selector(".cc_btn_accept_all")
    cookie_accept_btn.click()

    # Add finalizer to quit the webdriver instance
    request.addfinalizer(finalizer)

    timeout_process.start()
    return browser


def make_screenshot(driver, name):
    dir = os.path.join(CFG_TMPDIR, 'e2e')
    if not os.path.exists(dir):
        os.makedirs(dir)
    driver.save_screenshot(os.path.join(dir, name))


def e2e_assert(driver, assertion, message = None):
    """Wrapper for assert which will print the current page text if the assertion is false.
    This will allow us to see any errors which only occur on CI.
    """
    if not assertion:
        print('========== Failed assertion in selenium test. ===================================')

        if message:
            print('Assertion message: ' + message + '\n')

        print('Browser body text was:\n')
        print(driver.find_element_by_tag_name('body').text)
        print('\n================================================================================')

    assert assertion, message

def e2e_assert_url(driver, expected_route):
    expected_url = flask.url_for(expected_route, _external=True)
    e2e_assert(driver,
               expected_url in driver.current_url,
               "Should be at page " + expected_url + " but url was: " + driver.current_url)
