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

"""HEPData end to end testing of dashboard and administrative options."""
import csv
import io
import requests

from flask import url_for
from invenio_accounts.models import User
from invenio_db import db
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.submission import \
    get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.models import HEPSubmission

from .conftest import e2e_assert_url


def test_dashboard(live_server, logged_in_browser):
    """
    Test dashboard functions
    """
    browser = logged_in_browser

    non_admin_user = User(
        email='test2@hepdata.net',
        active=True
    )
    db.session.add(non_admin_user)
    db.session.commit()

    # Create some submissions so that there'll be something on the dashboard
    # and on 2 pages. Current user will be coordinator and uploader for most.
    for i in range(26):
        content = {'title': f'Dashboard Test {i}'}
        record_information = create_record(content)
        hepsubmission = get_or_create_hepsubmission(record_information["recid"], 1)
        user_account = non_admin_user.id if i == 0 else 1
        participant_record = SubmissionParticipant(email='test@hepdata.net',
                                                   status='primary',
                                                   role='uploader',
                                                   user_account=user_account,
                                                   publication_recid=record_information["recid"])
        db.session.add(hepsubmission)
        db.session.add(participant_record)

    db.session.commit()

    # Confirm there are 26 'todo' submissions
    submissions = HEPSubmission.query \
        .filter_by(overall_status='todo').all()
    assert len(submissions) == 26

    # Click on dashboard link
    browser.find_element(By.LINK_TEXT, 'Dashboard').click()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Check links in top section work
    # Submissions Overview link
    browser.find_element(By.LINK_TEXT, 'Submissions Overview').click()
    e2e_assert_url(browser, 'hep_dashboard.submissions')

    # Wait for graph to load
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#submission_vis svg"))
    )

    # Go back
    browser.back()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Edit Profile link
    browser.find_element(By.LINK_TEXT, 'Edit Profile').click()
    e2e_assert_url(browser, 'invenio_userprofiles.profile')

    # Go back
    browser.back()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Wait for submissions to load
    submissions_list = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "hep-submissions"))
    )
    submission_items = submissions_list.find_elements(By.CLASS_NAME, 'submission-item')
    assert len(submission_items) == 25

    # Check pagination works
    browser.find_element(By.CSS_SELECTOR, ".pagination-bar a[href='/dashboard/?page=2']").click()
    # Wait for loader, then new items appear
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, '.submission-item h4 a'),
            'Dashboard Test 0'
        )
    )
    # Should just be 1 submission on page 2
    submission_items = browser.find_elements(By.CLASS_NAME, 'submission-item')
    assert len(submission_items) == 1

    # Check settings modal appears
    submission_items[0].find_element(By.CLASS_NAME, 'manage-submission-trigger').click()
    manage_widget = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'manageWidget'))
    )
    
    assert manage_widget.find_element(By.CLASS_NAME,'modal-title').text == 'Manage Submission'

    # Check reminder email button works
    reminder_button = manage_widget.find_element_by_css_selector('.trigger-actions .btn-primary')
    assert reminder_button.get_attribute('data-action') == 'email'
    reminder_button.click()
    confirmation_message = manage_widget.find_element_by_id('confirmation_message').text
    assert confirmation_message == 'Are you sure you want to email this uploader?'
    confirmation_button = manage_widget.find_element_by_css_selector('.confirm-move-action')
    confirmation_button.click()
    assert not manage_widget.find_element_by_id('confirmation').is_displayed()

    # Close modal
    manage_widget.find_element(By.CSS_SELECTOR, '.modal-footer .btn-default').click()
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(manage_widget)
    )

    # Click delete button
    # Check settings modal appears
    submission_items[0].find_element(By.CLASS_NAME, 'delete-submission-trigger').click()
    delete_widget = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'deleteWidget'))
    )
    assert delete_widget.find_element(By.CLASS_NAME, 'modal-title').text == 'Delete Submission'
    # Confirm deletion
    delete_widget.find_element(By.CLASS_NAME, 'confirm-delete').click()
    # Wait for confirmation of deletion
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'delete-success'))
    )
    assert 'Submission will be deleted' in \
        delete_widget.find_element(By.CSS_SELECTOR, '#delete-success p').text

    # Should now be 25 submissions not 26
    db.session.flush()
    try:
        submissions = HEPSubmission.query \
            .filter_by(overall_status='todo').all()
    except Exception as e:
        # Roll back and try again
        db.session.rollback()
        submissions = HEPSubmission.query \
            .filter_by(overall_status='todo').all()

    assert len(submissions) == 25

    # Reload the dashboard (rather than waiting)
    browser.refresh()

    # Check permissions widget
    # Coordinator tab should have 5 items (restricted as we are user id 1)
    coordinator_pane = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, 'coordinator'))
    )
    coordinator_rows = coordinator_pane.find_elements(By.CLASS_NAME, 'row')
    assert len(coordinator_rows) == 5

    # Click on uploader pane - should be all 25 items
    browser.find_element(By.LINK_TEXT, 'uploader').click()
    uploader_pane = browser.find_element(By.ID, 'uploader')
    uploader_rows = uploader_pane.find_elements(By.CLASS_NAME, 'row')
    assert len(uploader_rows) == 25

    # Only first 5 should be visible
    assert all(row.is_displayed() for row in uploader_rows[:5])
    assert all(not row.is_displayed() for row in uploader_rows[5:])
    # Scroll down to find paginator
    ActionChains(browser).move_to_element(uploader_rows[4]).perform()
    # Click on last page
    uploader_pane.find_element(By.CSS_SELECTOR, ".pagination-bar li a[title=last]").click()
    # Now last 5 items should be visible
    assert all(not row.is_displayed() for row in uploader_rows[:20])
    assert all(row.is_displayed() for row in uploader_rows[20:])

    # Check CSV download works
    csv_button = browser.find_element(By.LINK_TEXT, 'Download Submissions CSV')
    download_url = csv_button.get_attribute("href")
    assert(download_url.endswith("/submissions/csv"))
    # We can't test file downloads via selenium on SauceLabs so we'll just
    # download it using requests and check it can be read as a CSV with the
    # right number of columns
    response = requests.get(
        download_url,
        cookies={c["name"]: c["value"] for c in browser.get_cookies()}
    )
    assert(response.status_code == 200)
    decoded_lines = response.content.decode('utf-8').splitlines()
    assert len(decoded_lines) == 5
    csv_reader = csv.reader(decoded_lines)
    for row in csv_reader:
        assert len(row) == 12

    # View the dashboard as the non-admin user
    # First scroll back to the top of the screen
    browser.execute_script("window.scrollTo(0,0);")
    admin_user_filter = browser.find_element(By.ID, 'admin-user-filter')
    admin_user_filter.send_keys('test')
    suggestions_div = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'tt-open'))
    )
    suggestions = suggestions_div.find_elements(By.CLASS_NAME, 'tt-suggestion')
    assert len(suggestions) == 2
    assert suggestions[0].text == 'test@hepdata.net'
    assert suggestions[1].text == 'test2@hepdata.net'
    suggestions[1].click()

    # Dashboard should reload with ?view_as_user=2 query param
    assert browser.current_url == url_for('hep_dashboard.dashboard',
        _external=True, view_as_user=non_admin_user.id)

    # Check banner appears at top of page
    banner = browser.find_element(By.CLASS_NAME, 'alert-info')
    assert banner.text == "You are logged in as test@hepdata.net but are currently viewing the " \
        "dashboard as user test2@hepdata.net. View as test@hepdata.net"

    # Wait for submissions to load - this user shouldn't have any
    submissions_list = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "hep-submissions"))
    )
    submission_items = submissions_list.find_elements(By.CLASS_NAME, 'submission-item')
    assert len(submission_items) == 0

    # Check permissions widget - should be a message saying no contributions
    permissions_div = browser.find_element(By.ID, 'permissions')
    assert permissions_div.text.startswith('No contributions to show')
