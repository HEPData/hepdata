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
import time
from datetime import datetime

import flask
from flask_security.utils import hash_password
import pytest
from invenio_accounts.models import User, Role
from invenio_db.shared import metadata, SQLAlchemy as InvenioSQLAlchemy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.command import Command
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy_utils.functions import create_database, database_exists
from time import sleep

from hepdata.config import CFG_TMPDIR, RUN_SELENIUM_LOCALLY
from hepdata.ext.opensearch.api import reindex_all
from hepdata.factory import create_app
from tests.conftest import get_identifiers, import_default_data


# Override Invenio-DB's SQLAlchemy object to set pool_pre_ping to True to avoid
# issues with dropped connection pools
class SQLAlchemy(InvenioSQLAlchemy):
    def apply_pool_defaults(self, app, options):
        # See https://github.com/pallets/flask-sqlalchemy/issues/589#issuecomment-361075700
        options = super().apply_pool_defaults(app, options)
        options["pool_pre_ping"] = True
        return options



db = SQLAlchemy(metadata=metadata)

multiprocessing.set_start_method('fork')

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
        OPENSEARCH_INDEX="hepdata-main-test",
        SUBMISSION_INDEX='hepdata-submission-test',
        AUTHOR_INDEX='hepdata-authors-test',
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg2://hepdata:hepdata@' + test_db_host + '/hepdata_test'),
        APP_ENABLE_SECURE_HEADERS=False,
        E2E_TESTING=True
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
            user = User(
                email='test@hepdata.net',
                password=hash_password('hello1'),
                active=True,
                confirmed_at=datetime.now()
            )
            admin_role = Role(name='admin')
            coordinator_role = Role(name='coordinator')

            user.roles.append(admin_role)
            user.roles.append(coordinator_role)

            db.session.add(admin_role)
            db.session.add(coordinator_role)
            db.session.add(user)
            db.session.commit()

        import_default_data(app, get_e2e_identifiers())

    def teardown():
        with app.app_context():
            db.engine.dispose()
            db.drop_all()
            ctx.pop()

    request.addfinalizer(teardown)

    return app


def get_e2e_identifiers():
    return get_identifiers() + [{
        "hepdata_id": "ins1883075", "inspire_id": '1883075',
         "title": "Search for long-lived particles decaying in the CMS endcap muon detectors in proton-proton collisions at  13 TeV",
         "data_tables": 15
    }]


@pytest.fixture()
def e2e_identifiers(app):
    return get_e2e_identifiers()


@pytest.fixture()
def search_tests(app):
    return [{"search_term": "collisions", "exp_collab_facet": "BELLE",
             "exp_hepdata_id": "ins1245023", "exp_table_count": 0},
            {"search_term": "leptons", "exp_collab_facet": "D0",
             "exp_hepdata_id": "ins1283842", "exp_table_count": 0},
            {"search_term": "reactions:PBAR P --> LEPTON JETS X",
             "exp_collab_facet": "D0", "exp_hepdata_id": "ins1283842",
             "exp_table_count": 3},
            {"search_term": "observables:SIG", "exp_collab_facet": "BELLE",
             "exp_hepdata_id": "ins1245023", "exp_table_count": 1}]


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

    if not RUN_SELENIUM_LOCALLY:
        remote_url = "https://ondemand.eu-central-1.saucelabs.com:443/wd/hub"
        options = webdriver.ChromeOptions()
        options.browser_version = '143'
        options.platform_name = 'Windows 11'
        local_tunnel_name = os.environ.get('SAUCE_USERNAME', '') + '_tunnel_name'
        sauce_options = {
            'extendedDebugging': True,
            'screenResolution': '1280x1024',
            'name': request.node.name,
            'build': os.environ.get('GITHUB_RUN_ID', datetime.utcnow().strftime("%Y-%m-%d %H:00ish")),
            'username': os.environ.get('SAUCE_USERNAME', ''),
            'accessKey': os.environ.get('SAUCE_ACCESS_KEY', ''),
            'tunnelName': os.environ.get('GITHUB_RUN_ID', local_tunnel_name),
        }

        for key in ['username', 'accessKey']:
            if sauce_options[key] == '':
                raise Exception(f"Sauce {key} is not in Environment")

        options.set_capability('sauce:options', sauce_options)
        # This creates a webdriver object to send to Sauce Labs including the desired capabilities
        browser = webdriver.Remote(remote_url, options=options)
    else:
        # Run tests locally instead of on Sauce Labs (requires local chromedriver installation).
        browser = getattr(webdriver, request.param)()

    browser.set_window_size(1280, 1024)
    browser.implicitly_wait(10)  # seconds

    # Go to homepage and click cookie accept button so cookie bar is out of the way
    browser.get(flask.url_for('hepdata_theme.index', _external=True))
    wait = WebDriverWait(browser, 10)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".cc_btn_accept_all")))
    sleep(1)
    cookie_accept_btn = browser.find_element(By.CSS_SELECTOR, ".cc_btn_accept_all")
    cookie_accept_btn.click()

    # Add finalizer to quit the webdriver instance
    request.addfinalizer(finalizer)

    timeout_process.start()
    yield browser

    # Check browser logs before quitting
    log = browser.execute(Command.GET_LOG, {"type": "browser"})["value"]

    # Filter out error message for:
    # WARNING: security - Error with Permissions-Policy header:
    # Origin trial controlled feature not enabled: 'interest-cohort'
    log = [t for t in log if 'interest-cohort' not in t['message']]

    # Filter out error message for:
    # SEVERE: http://localhost:5555/favicon.ico - Failed to load resource:
    # the server responded with a status of 404 (Not Found)
    log = [t for t in log if 'favicon.ico' not in t['message']]

    assert len(log) == 0, \
        "Errors in browser log:\n" + \
        "\n".join([f"{line['level']}: {line['message']}" for line in log])


@pytest.fixture()
def logged_in_browser(env_browser):
    # Log in
    env_browser.get(flask.url_for('security.login', _external=True))
    e2e_assert_url(env_browser, 'security.login')

    login_form = env_browser.find_element(By.NAME, 'login_user_form')
    login_form.find_element(By.NAME, 'email').send_keys('test@hepdata.net')
    login_form.find_element(By.NAME, 'password').send_keys('hello1')
    login_form.submit()

    # Check we're back at the homepage
    e2e_assert_url(env_browser, 'hepdata_theme.index')

    return env_browser


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
        print(driver.find_element(By.TAG_NAME, 'body').text)
        print('\n================================================================================')

    assert assertion, message

def e2e_assert_url(driver, expected_route):
    expected_url = flask.url_for(expected_route, _external=True)
    e2e_assert(driver,
               expected_url in driver.current_url,
               "Should be at page " + expected_url + " but url was: " + driver.current_url)
