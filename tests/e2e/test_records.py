#
# This file is part of HEPData.
# Copyright (C) 2021 CERN.
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

"""HEPData end to end testing of updating/reviewing records"""

import os.path

import flask
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from hepdata.modules.submission.models import HEPSubmission
from invenio_db import db

from .conftest import e2e_assert_url


def test_record_update(live_server, logged_in_browser):
    """
    Test making changes to a record.
    """
    browser = logged_in_browser
    browser.file_detector = LocalFileDetector()

    inspire_id = '1283842'
    # Check there's just 1 version of our submission
    submissions = HEPSubmission.query.filter_by(
        inspire_id=inspire_id).all()
    assert len(submissions) == 1
    assert submissions[0].version == 1

    # Go to existing (default) record and create a new version
    record_url = flask.url_for(
        'hepdata_records.get_metadata_by_alternative_id',
        recid=f'ins{inspire_id}', _external=True)
    browser.get(record_url)
    browser.find_element(By.CSS_SELECTOR,
        "button.btn-danger[data-target='#reviseSubmission']").click()
    revise_submission_dialog = browser.find_element(By.ID, 'reviseSubmission')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(revise_submission_dialog)
    )

    # Check for warning about a new version
    assert "This submission is already finished." in \
        revise_submission_dialog.find_element(By.ID, 'revise-confirm').text

    # Click "Revise Submission" button and wait for response
    revise_submission_dialog.find_element(By.CSS_SELECTOR, "#revise-confirm button[type='submit']").click()
    revise_success = browser.find_element(By.ID, 'revise-success')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(revise_success)
    )
    assert revise_success.find_element(By.TAG_NAME, 'p').text \
        .startswith("Version 2 created.\nThis window will close in ")

    # Refresh record page (to avoid waiting)
    browser.get(record_url)

    # Should now be 2 versions of our submission
    submissions = HEPSubmission.query \
        .filter_by(inspire_id=inspire_id) \
        .order_by(HEPSubmission.created).all()
    assert len(submissions) == 2
    assert submissions[0].version == 1
    assert submissions[0].overall_status == 'finished'
    assert submissions[1].version == 2
    assert submissions[1].overall_status == 'todo'

    # Upload a new file
    upload = browser.find_element(By.ID, 'root_file_upload')
    ActionChains(browser).move_to_element(upload).perform()
    upload.send_keys(os.path.abspath("tests/test_data/TestHEPSubmission.zip"))
    browser.find_element(By.CSS_SELECTOR, 'form[name=upload-form] input[type=submit]').click()

    # Wait for page reload
    WebDriverWait(browser, 15).until(
        EC.staleness_of(upload)
    )
    alert = browser.find_element(By.CLASS_NAME, 'alert-info')
    assert alert.text == "File saved. You will receive an email when the file has been processed."

    # Run common checks
    _check_record_common(browser)

    # Add some reviews
    # Check initial status of Table 1 is "ToDo"
    table1_summary = browser.find_element(By.ID, 'table-list') \
        .find_element(By.CLASS_NAME, 'Table1')
    table1_id = table1_summary.get_attribute('id')
    table1_status = table1_summary.find_element(By.ID, f'{table1_id}-status')
    assert "todo" in table1_status.get_attribute('class')

    # Change review status
    browser.find_element(By.ID, 'reviewer-button').click()
    reviews_view = browser.find_element(By.CLASS_NAME, 'reviews-view')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(reviews_view)
    )
    reviews_view.find_element(By.ID, 'attention-option').click()
    if "attention" not in table1_status.get_attribute('class'):
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"span[id='{table1_id}-status'][class*='attention']")
            )
        )
    assert "attention" in table1_status.get_attribute('class')

    # Send a message
    message_box = reviews_view.find_element(By.ID, 'message')
    ActionChains(browser).move_to_element(message_box).perform()
    message_box.send_keys("This needs to change!")
    reviews_view.find_element(By.ID, 'save_no_email').click()
    # Wait until message appears
    message = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '#review_messages .message-content')
        )
    )
    assert "This needs to change!" in message.text
    assert "test@hepdata.net" in message.find_element(By.CLASS_NAME, 'reviewer').text
    # Close review pane
    browser.find_element(By.ID, 'reviewer-button').click()

    # Switch to Table 2 and change review status
    table2_summary = browser.find_element(By.ID, 'table-list') \
        .find_element(By.CLASS_NAME, 'Table2')
    table2_summary.click()
    table2_id = table2_summary.get_attribute('id')
    table2_status = table2_summary.find_element(By.ID, f'{table2_id}-status')
    assert "todo" in table2_status.get_attribute('class')

    # Change review status
    browser.find_element(By.ID, 'reviewer-button').click()
    reviews_view = browser.find_element(By.CLASS_NAME, 'reviews-view')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(reviews_view)
    )
    reviews_view.find_element(By.ID, 'passed-option').click()
    if "passed" not in table2_status.get_attribute('class'):
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"span[id='{table2_id}-status'][class*='passed']")
            )
        )
    assert "passed" in table2_status.get_attribute('class')

    # Check "Notify Coordinator" is hidden
    assert not browser.find_element(By.ID, 'notify-coordinator-btn').is_displayed()

    # Click "Approve All"
    browser.find_element(By.ID, 'approve-all-btn').click()
    approve_all_modal = browser.find_element(By.ID, 'approveAllTables')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(approve_all_modal)
    )
    approve_all_modal.find_element(By.ID, 'confirmApproveAll').click()
    approve_all_modal.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()

    # Wait for page reload
    WebDriverWait(browser, 10).until(
        EC.staleness_of(approve_all_modal)
    )
    # Check all statuses are now 'passed'
    review_statuses = browser.find_element(By.ID, 'table-list') \
        .find_elements(By.CLASS_NAME, 'review-status')
    for element in review_statuses:
        assert "passed" in element.get_attribute('class')

    # Check that "Approve all" button is not visible and "Notify Coordinator"
    # is now visible
    assert not browser.find_element(By.ID, 'approve-all-btn').is_displayed()
    assert browser.find_element(By.ID, 'notify-coordinator-btn').is_displayed()

    # Delete the new version
    # Open admin slider
    browser.find_element(By.ID, 'admin-button').click()
    admin_view = browser.find_element(By.CLASS_NAME, 'admin-view')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(admin_view)
    )
    # Click "Delete"
    admin_view.find_element(By.CSS_SELECTOR,
        "button.btn-danger[data-target='#deleteWidget']"
        ).click()
    # Wait for modal to load
    delete_widget = browser.find_element(By.ID, 'deleteWidget')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(delete_widget)
    )
    assert delete_widget.find_element(By.CSS_SELECTOR, '#delete-confirm p').text \
        .startswith("Are you sure you want to delete the latest version of this submission?")
    # Click "Delete now"
    delete_widget.find_element(By.CLASS_NAME, 'confirm-delete').click()
    # Wait for confirmation of deletion
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element((By.ID, 'delete-success'), 'Submission will be deleted')
    )

    # Should now only be 1 version of our submission
    db.session.flush()
    try:
        submissions = HEPSubmission.query \
            .filter_by(inspire_id=inspire_id).all()
    except Exception as e:
        # Roll back and try again
        db.session.rollback()
        submissions = HEPSubmission.query \
            .filter_by(inspire_id=inspire_id).all()
    assert len(submissions) == 1
    assert submissions[0].version == 1
    assert submissions[0].overall_status == 'finished'


def test_sandbox(live_server, logged_in_browser):
    """
    Test adding, modifying and deleting a sandbox record
    """
    browser = logged_in_browser
    browser.file_detector = LocalFileDetector()

    # Go to sandbox
    sandbox_url = flask.url_for('hepdata_records.sandbox', _external=True)
    browser.get(sandbox_url)
    e2e_assert_url(browser, 'hepdata_records.sandbox')

    # Check there are no past sandbox submissions
    assert browser.find_element(By.ID, 'past_submissions') \
        .find_elements(By.XPATH, ".//*") == []

    # Try uploading a file
    upload = browser.find_element(By.ID, 'root_file_upload')
    ActionChains(browser).move_to_element(upload).perform()
    upload.send_keys(os.path.abspath("tests/test_data/TestHEPSubmission.zip"))
    browser.find_element(By.CLASS_NAME, 'btn-primary').click()

    # Should redirect to record page with confirmation message
    WebDriverWait(browser, 15).until(
        EC.url_matches(f'{sandbox_url}/\\d+')
    )
    alert = browser.find_element(By.CLASS_NAME, 'alert-info')
    assert alert.text == "File saved. You will receive an email when the file has been processed."

    # Record should have been processed immediately by test celery runner
    # so we can check its contents
    _check_record_common(browser)

    # Go back to the sandbox
    browser.get(sandbox_url)

    # Check that past submissions column now has a child
    past_submissions_div = browser.find_element(By.ID, 'past_submissions')
    assert len(past_submissions_div.find_elements(By.CLASS_NAME, 'col-md-10')) == 1

    # Delete the sandbox record
    past_submissions_div.find_element(By.CLASS_NAME, 'delete_button').click()
    delete_modal = browser.find_element(By.ID, 'deleteWidget')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(delete_modal)
    )
    delete_modal.find_element(By.CLASS_NAME, 'confirm-delete').click()
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#delete-success p'), 'Submission will be deleted')
    )

    # Refresh sandbox page (to avoid waiting)
    browser.get(sandbox_url)

    # Check there are no past sandbox submissions
    assert browser.find_element(By.ID, 'past_submissions') \
        .find_elements(By.XPATH, ".//*") == []


def _check_record_common(browser):
    """
    Check record features that are common to standard and sandbox records.
    Browser should be at relevant record URL before calling this function.
    """
    assert browser.find_element(By.CLASS_NAME, 'record-abstract-content').text \
        .startswith('CERN-LHC.  Measurements of the cross section  for ZZ production')
    table_items = browser.find_element(By.ID, 'table-list').find_elements(By.TAG_NAME, 'li')
    assert len(table_items) == 8
    assert "active" in table_items[0].get_attribute("class")
    assert table_items[0].find_element(By.TAG_NAME, 'h4').text == "Table 1"
    assert table_items[0].find_element(By.TAG_NAME, 'p').text == "Data from Page 17 of preprint"
    table_content = browser.find_element(By.ID, 'hepdata_table_content')
    assert table_content.find_element(By.ID, 'table_name').text == "Table 1"
    assert table_content.find_element(By.ID, 'table_location').text == "Data from Page 17 of preprint"

    # Check resources load (using button for table)
    # modal content should not be visible beforehand
    modal_content = browser.find_element(By.ID, 'resourceModal')
    assert not modal_content.is_displayed()
    table_content.find_element(By.ID, 'show_resources').click()
    WebDriverWait(browser, 10).until(
        EC.visibility_of(modal_content)
    )
    assert modal_content.find_element(By.ID, 'additionalResource').text == \
        "Additional Publication Resources"
    assert modal_content.find_element(By.ID, 'selected_resource_item').text == \
        "Table 1"

    resource_list_items = modal_content \
        .find_element(By.ID, 'resource-list-items') \
        .find_elements(By.TAG_NAME, 'li')

    # Check we can select a different table/common resources
    resource_list_items[0].click()
    assert modal_content.find_element(By.ID, 'selected_resource_item').text == \
        "Common Resources"
    resource_list_items[8].click()
    assert modal_content.find_element(By.ID, 'selected_resource_item').text == \
        "Table 8"

    # Check filtering by table name
    assert len([e for e in resource_list_items if e.is_displayed()]) == 9
    filter_field = modal_content.find_element(By.ID, 'resource-filter-input')

    # Filter by 'tab'. First item ("Common resources") should fade out
    filter_field.send_keys('tab')
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(resource_list_items[0])
    )
    assert len([e for e in resource_list_items if e.is_displayed()]) == 8

    # Clear filter. First item should become visible
    filter_field.send_keys('\b\b\b')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(resource_list_items[0])
    )
    assert len([e for e in resource_list_items if e.is_displayed()]) == 9

    # Filter by 'res'. All items except first ("Common resources") should fade out
    filter_field.send_keys('res')
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(resource_list_items[1])
    )
    assert len([e for e in resource_list_items if e.is_displayed()]) == 1

    # Close the modal
    modal_content.find_element(By.CLASS_NAME, 'close').click()
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(modal_content)
    )

    # Try uploading another file
    browser.find_element(By.CSS_SELECTOR, "button.btn-success[data-target='#uploadDialog']") \
        .click()
    upload_dialog = browser.find_element(By.ID, 'uploadDialog')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(upload_dialog)
    )
    upload = upload_dialog.find_element(By.ID, 'file_upload_field')
    ActionChains(browser).move_to_element(upload).perform()
    upload.send_keys(os.path.abspath("tests/test_data/sample.oldhepdata"))
    upload_dialog.find_element(By.CSS_SELECTOR, 'input[type=submit]').click()
    # Wait for page reload
    WebDriverWait(browser, 15).until(
        EC.staleness_of(upload_dialog)
    )
    alert = browser.find_element(By.CLASS_NAME, 'alert-info')
    assert alert.text == "File saved. You will receive an email when the file has been processed."
