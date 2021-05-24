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

    # Create some submissions so that there'll be something on the dashboard
    # and on 2 pages. Current user will be coordinator and uploader.
    for i in range(26):
        content = {'title': f'Dashboard Test {i}'}
        record_information = create_record(content)
        hepsubmission = get_or_create_hepsubmission(record_information["recid"], 1)
        participant_record = SubmissionParticipant(email='test@hepdata.net',
                                                   status='primary',
                                                   role='uploader',
                                                   user_account=1,
                                                   publication_recid=record_information["recid"])
        db.session.add(hepsubmission)
        db.session.add(participant_record)

    db.session.commit()

    # Confirm there are 26 'todo' submissions
    submissions = HEPSubmission.query \
        .filter_by(overall_status='todo').all()
    assert len(submissions) == 26

    # Click on dashboard link
    browser.find_element_by_link_text('Dashboard').click()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Check links in top section work
    # Submissions Overview link
    browser.find_element_by_link_text('Submissions Overview').click()
    e2e_assert_url(browser, 'hep_dashboard.submissions')

    # Wait for graph to load
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#submission_vis svg"))
    )

    # Go back
    browser.back()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Edit Profile link
    browser.find_element_by_link_text('Edit Profile').click()
    e2e_assert_url(browser, 'invenio_userprofiles.profile')

    # Go back
    browser.back()
    e2e_assert_url(browser, 'hep_dashboard.dashboard')

    # Wait for submissions to load
    submissions_list = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "hep-submissions"))
    )
    submission_items = submissions_list.find_elements_by_class_name('submission-item')
    assert len(submission_items) == 25

    # Check pagination works
    browser.find_element_by_css_selector(".pagination-bar a[href='/dashboard/?page=2']").click()
    # Wait for loader, then new items appear
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, '.submission-item h4 a'),
            'Dashboard Test 0'
        )
    )
    # Should just be 1 submission on page 2
    submission_items = browser.find_elements_by_class_name('submission-item')
    assert len(submission_items) == 1

    # Check settings modal appears
    submission_items[0].find_element_by_class_name('manage-submission-trigger').click()
    manage_widget = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'manageWidget'))
    )
    assert manage_widget.find_element_by_class_name('modal-title').text == 'Manage Submission'
    # Close modal
    manage_widget.find_element_by_css_selector('.modal-footer .btn-default').click()
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(manage_widget)
    )

    # Click delete button
    # Check settings modal appears
    submission_items[0].find_element_by_class_name('delete-submission-trigger').click()
    delete_widget = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'deleteWidget'))
    )
    assert delete_widget.find_element_by_class_name('modal-title').text == 'Delete Submission'
    # Confirm deletion
    delete_widget.find_element_by_class_name('confirm-delete').click()
    # Wait for confirmation of deletion
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, 'delete-success'))
    )
    assert 'Submission deleted' in \
        delete_widget.find_element_by_css_selector('#delete-success p').text

    # Should now be 25 submissions not 26
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
    coordinator_rows = coordinator_pane.find_elements_by_class_name('row')
    assert len(coordinator_rows) == 5

    # Click on uploader pane - should be all 25 items
    browser.find_element_by_link_text('uploader').click()
    uploader_pane = browser.find_element_by_id('uploader')
    uploader_rows = uploader_pane.find_elements_by_class_name('row')
    assert len(uploader_rows) == 25

    # Only first 5 should be visible
    assert all(row.is_displayed() for row in uploader_rows[:5])
    assert all(not row.is_displayed() for row in uploader_rows[5:])
    # Scroll down to find paginator
    ActionChains(browser).move_to_element(uploader_rows[4]).perform()
    # Click on last page
    uploader_pane.find_element_by_css_selector(".pagination-bar li a[title=last]").click()
    # Now last 5 items should be visible
    assert all(not row.is_displayed() for row in uploader_rows[:20])
    assert all(row.is_displayed() for row in uploader_rows[20:])
