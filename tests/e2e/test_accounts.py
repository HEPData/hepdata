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

"""HEPData end to end testing of accounts."""
import flask

from .conftest import e2e_assert, e2e_assert_url
from invenio_accounts import testutils
from itsdangerous import URLSafeTimedSerializer
from flask_security import utils
from passlib.context import CryptContext

def test_user_registration_and_login(live_server, env_browser):
    """E2E user registration and login test."""
    browser = env_browser
    # 1. Go to user registration page
    browser.get(flask.url_for('security.register', _external=True))
    e2e_assert_url(browser, 'security.register')

    # 2. Input user data
    signup_form = browser.find_element_by_name('register_user_form')
    input_email = signup_form.find_element_by_name('email')
    input_password = signup_form.find_element_by_name('password')
    # input w/ name "email"
    # input w/ name "password"
    user_email = 'user@hepdata.net'
    user_password = '12345_SIx'
    input_email.send_keys(user_email)
    input_password.send_keys(user_password)

    # 3. submit form
    signup_form.submit()

    # ...and get a message saying to expect an email
    success_element = browser.find_element_by_css_selector('.alert-success')
    assert(success_element is not None)
    assert(success_element.text == 'Thank you. Confirmation instructions have been sent to {}.'.format(user_email))

    # 3.5: After registering we should not yet be logged in.
    e2e_assert(browser, not testutils.webdriver_authenticated(browser),
               'Should not be authenticated')

    # 4. go to login-form
    browser.get(flask.url_for('security.login', _external=True))
    e2e_assert_url(browser, 'security.login')

    login_form = browser.find_element_by_name('login_user_form')
    # 5. input registered info
    login_form.find_element_by_name('email').send_keys(user_email)
    login_form.find_element_by_name('password').send_keys(user_password)
    # 6. Submit!
    login_form.submit()

    # 7. We should not yet be able to log in as we haven't confirmed the email
    error_element = browser.find_element_by_css_selector('.alert-danger')
    assert(error_element is not None)
    assert('Email requires confirmation.' in error_element.text)

    e2e_assert(browser,
               not testutils.webdriver_authenticated(browser),
               'Should not be authenticated')

    # 8. Check that the resend confirmation link works
    browser.get(flask.url_for('security.send_confirmation', _external=True))
    e2e_assert_url(browser, 'security.send_confirmation')
    email_confirm_form = browser.find_element_by_name('send_confirmation_form')
    # 8a. input registered info
    email_confirm_form.find_element_by_name('email').send_keys(user_email)
    # 8b. Submit!
    email_confirm_form.submit()

    info_element = browser.find_element_by_css_selector('.alert-info')
    assert(info_element is not None)
    assert('Confirmation instructions have been sent to %s.' % user_email
           in info_element.text)

    # 9a Generate a confirmation token (this is how it's done in flask_security)
    data = ['2', utils.hash_data(user_email)]
    serializer = URLSafeTimedSerializer(
        secret_key="CHANGE_ME",
        salt="CHANGE_ME"
    )
    token = serializer.dumps(data)

    # 9b Go to the confirmation URL with our token
    browser.get(flask.url_for('security.confirm_email', token=token, _external=True))

    # 9c Check that we're on the dashboard and we've got a success message
    e2e_assert_url(browser, 'hep_dashboard.dashboard')
    success_element = browser.find_element_by_css_selector('.alert-success')
    assert(success_element is not None)
    assert('Thank you. Your email has been confirmed.' in success_element.text)

    # 9d We should now be logged in
    e2e_assert(browser,
               testutils.webdriver_authenticated(browser),
               'Should be authenticated')

    # 10. logout.
    browser.get(flask.url_for('security.logout', _external=True))
    e2e_assert(browser, not testutils.webdriver_authenticated(browser),
               'Should not be authenticated')

    # 11. go back to login-form
    browser.get(flask.url_for('security.login', _external=True))
    e2e_assert_url(browser, 'security.login')

    login_form = browser.find_element_by_name('login_user_form')
    # 11a. input registered info
    login_form.find_element_by_name('email').send_keys(user_email)
    login_form.find_element_by_name('password').send_keys(user_password)
    # 11b. Submit!
    # check if authenticated at `flask.url_for('security.change_password')`
    login_form.submit()

    e2e_assert(browser, testutils.webdriver_authenticated(browser))

    # 12. check we can access the change password screen
    browser.get(flask.url_for('security.change_password', _external=True))
    e2e_assert_url(browser, 'security.change_password')

    # 13. logout.
    browser.get(flask.url_for('security.logout', _external=True))
    e2e_assert(browser, not testutils.webdriver_authenticated(browser),
               'Should not be authenticated')
