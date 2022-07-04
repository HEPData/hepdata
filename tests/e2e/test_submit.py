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

"""HEPData end to end testing of record submission."""
import flask
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from hepdata.modules.submission.api import get_submission_participants_for_record
from hepdata.modules.submission.models import HEPSubmission

from .conftest import e2e_assert, e2e_assert_url


def test_create_submission(live_server, logged_in_browser):
    """Create submission test"""
    browser = logged_in_browser
    inspire_id = '1830840'

    # First confirm there are no submissions for our inspire id
    submissions = HEPSubmission.query.filter_by(inspire_id=inspire_id).all()
    assert len(submissions) == 0

    # Click "submit"
    submit_link = browser.find_element(By.LINK_TEXT, 'Submit')
    submit_link.click()

    # Check we're at the submission page
    e2e_assert_url(browser, 'submission.submit_ui')
    inspire_details_div = browser.find_element(By.ID, 'inspire_details')
    assert "Do you have an Inspire record associated with your submission?" \
        in inspire_details_div.text
    # Click "Yes" and check continue button appears
    browser.find_element(By.ID, 'has_inspire').click()
    continue_button = browser.find_element(By.ID, 'continue_btn')
    e2e_assert(browser, not continue_button.is_enabled())

    # Fill in inspire id and check continue button is now enabled
    browser.find_element(By.ID, 'inspire_id').send_keys(inspire_id)
    e2e_assert(browser, continue_button.is_enabled())

    # Click 'continue'
    continue_button.click()

    # Wait for inspire details to load
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#inspire-result .publication-info"))
    )

    # Click continue and wait for animation to finish
    browser.find_element(By.ID, 'preview_continue_btn').click()
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#reviewers_uploaders h4"))
    )

    # Check for reviewer/uploader form
    reviewers_uploaders_title = browser.find_element(By.CSS_SELECTOR, '#reviewers_uploaders h4')
    assert "Please specify the Uploader and Reviewer for this submission" \
        in reviewers_uploaders_title.text

    # Fill in uploader/reviewer and submit
    browser.find_element(By.ID, 'uploader_name').send_keys('Ursula Uploader')
    browser.find_element(By.ID, 'uploader_email').send_keys('uu@hepdata.net')
    browser.find_element(By.ID, 'reviewer_name').send_keys('Rachel Reviewer')
    browser.find_element(By.ID, 'reviewer_email').send_keys('rr@hepdata.net')

    # Click continue and wait for animation to finish
    browser.find_element(By.ID, 'people_continue_btn').click()
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#uploader_message h4"))
    )

    # Add message for uploader
    browser.find_element(By.ID, 'uploader-message-input').send_keys('Please could you upload something?')

    # Click continue and wait for animation to finish
    browser.find_element(By.ID, 'message_continue_btn').click()
    submission_state_p = WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "#submission_state p"),
            "You are about to create a submission for")
    )

    # Click continue and wait for animation to finish
    browser.find_element(By.ID, 'submit_btn').click()
    submission_state_p = WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "#submission_state p"),
            "Submission Complete!"
        )
    )

    # Check that submission has been created in DB
    submissions = HEPSubmission.query.filter_by(
        inspire_id=inspire_id).all()
    assert len(submissions) == 1
    assert submissions[0].overall_status == 'todo'
    assert submissions[0].version == 1
    participants = sorted(
        get_submission_participants_for_record(submissions[0].publication_recid),
        key=lambda p: p.role
    )
    assert participants[0].role == "reviewer"
    assert participants[0].email == "rr@hepdata.net"
    assert participants[0].status == "primary"
    assert participants[1].role == "uploader"
    assert participants[1].email == "uu@hepdata.net"
    assert participants[1].status == "primary"

    # Try to create another submission with the same inspire id
    browser.find_element(By.ID, 'another_submission').click()
    e2e_assert_url(browser, 'submission.submit_ui')
    browser.find_element(By.ID, 'has_inspire').click()
    browser.find_element(By.ID, 'inspire_id').send_keys(inspire_id)
    continue_button = browser.find_element(By.ID, 'continue_btn')
    continue_button.click()
    # Wait for alert to appear
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#inspire-result .alert-danger"))
    )
    alert = browser.find_element(By.CSS_SELECTOR, "#inspire-result .alert-danger")
    assert alert.text == 'A record with this Inspire ID already exists in HEPData.'
    record_link = alert.find_element(By.TAG_NAME, 'a')
    assert record_link.get_attribute('href').endswith(f'/record/{submissions[0].publication_recid}')
