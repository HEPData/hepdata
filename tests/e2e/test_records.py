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
import shutil
import time

import flask
import os
import re
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from hepdata.config import HEPDATA_DOI_PREFIX
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.submission.models import HEPSubmission, RelatedRecid, DataSubmission, RelatedTable, \
    SubmissionObserver
from hepdata.modules.dashboard.api import create_record_for_dashboard
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission, process_submission_directory
from hepdata.modules.records.utils.workflow import create_record

from invenio_accounts.models import User
from invenio_db import db

from hepdata.modules.submission.views import process_submission_payload
from .conftest import e2e_assert_url
from ..conftest import create_blank_test_record, create_test_record


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
    db.session.flush()
    try:
        submissions = HEPSubmission.query.filter_by(inspire_id=inspire_id).order_by(HEPSubmission.created).all()
    except Exception as e:
        # Roll back and try again
        db.session.rollback()
        submissions = HEPSubmission.query.filter_by(inspire_id=inspire_id).order_by(HEPSubmission.created).all()
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


def test_related_records(live_server, logged_in_browser):
    """
        Test inserting two new submissions, and testing related
        recid/doi links display on the records page and link correctly.
    """
    browser = logged_in_browser
    # Dictionary to store the generated data.
    # The two objects should have flipped recid/expected values
    # i.e. Related to each other
    # TODO - Maybe make expected_number a list, to allow for testing of multiple expected values.
    test_data = [
        {"recid": None,  "submission": None, "related_recid": None, "submission_number": 1, "expected_number": 2},
        {"recid": None,  "submission": None, "related_recid": None, "submission_number": 2, "expected_number": 1}
    ]
    # Creates two records.
    for test in test_data:
        record_information = create_record(
            {'journal_info': 'Journal', 'title': f"Test Record {test['submission_number']}"})
        test['submission'] = get_or_create_hepsubmission(record_information['recid'])
        # Set overall status to finished so related data appears on dashboard
        test['submission'].overall_status = 'finished'
        test['recid'] = record_information['recid']
        record = get_record_by_id(test['recid'])
        user = User(email=f'test@test.com', password='hello1', active=True,
                    id=1)
        test_submissions = {}
        create_record_for_dashboard(record['recid'], test_submissions, user)

    # Recids for the test are set dynamically, based on what comes out of the minter
    # TODO - Would need to be changed to extend for more than one-to-one cases
    test_data[0]['related_recid'] = test_data[1]['recid']
    test_data[1]['related_recid'] = test_data[0]['recid']

    for test in test_data:
        recid = test['submission'].publication_recid
        # Create the mock related record ID data
        related = RelatedRecid(this_recid=recid,
            related_recid=test['related_recid'])
        test['submission'].related_recids.append(related)

        # Generate the DOI for the test DataSubmission object
        doi_string = f"{HEPDATA_DOI_PREFIX}/hepdata.{recid}.v1/t1"

        # Create a test DataSubmission object
        datasubmission = DataSubmission(
            name=f"Test Table {test['submission_number']}",
            location_in_publication="Somewhere",
            data_file=1,
            publication_recid=recid,
            associated_recid=recid,
            doi=doi_string,
            version=1,
            description=f"Test Description {test['submission_number']}")

        # Generate the test DOI string for the related DOI
        related_doi_string = f"{HEPDATA_DOI_PREFIX}/hepdata.{test['related_recid']}.v1/t1"

        # Create a test RelatedTable object and add it to the DataSubmission
        related_table = RelatedTable(table_doi=doi_string, related_doi=related_doi_string)
        datasubmission.related_tables.append(related_table)

        db.session.add_all([related, datasubmission, related_table])

    db.session.commit()

    # Begin testing
    for test in test_data:
        # Load up the Record page.
        record_url = flask.url_for('hepdata_records.get_metadata_by_alternative_id',
                                   recid=test['submission'].publication_recid, _external=True)
        browser.get(record_url)
        # The page elements to test and their type (Record/Data)
        related_elements = [
            {'id':'related-recids', 'type':'recid'},
            {'id':'related-to-this-recids', 'type':'recid'},
            {'id':'related-tables', 'type':'doi'},
            {'id':'related-to-this-tables', 'type':'doi'}
        ]

        for element in related_elements:
            html_element = browser.find_element(By.ID, element['id'])
            # Get the related data list html based on the current element
            data_list = html_element.find_element(By.CLASS_NAME, 'related-list')
            list_items = data_list.find_elements(By.TAG_NAME, 'li')

            # There should be only one entry for each related test category
            assert len(list_items) == 1

            url_tag = list_items[0].find_element(By.TAG_NAME, 'a')
            # Get the URL of the found `li` tag.
            url_loc = url_tag.get_attribute('href')
            # Expected ul and a tag contents differ based on which elements are tested
            # Records expect a link to the HEPData site. Tables link to doi.org
            if element['type'] == 'recid':
                # Check the URL against the regex
                pattern = rf"^.+/record/{test['related_recid']}$"
                assert re.match(pattern, url_loc)
                # Check that the tag text is the expected string
                # The result will be the string "Test Paper(X)" Where X is the ID.
                assert list_items[0].text == str(test['related_recid'])
                # Check the expected title of the related record tag
                assert url_tag.get_attribute('title') == f"Test Record {test['expected_number']}"

            elif element['type'] == 'doi':
                # Generate the test DOI string
                # Currently only testing v1/t1, maybe needs to be extended.
                related_doi_check = f"{HEPDATA_DOI_PREFIX}/hepdata.{test['related_recid']}.v1/t1"
                # Generate expected DOI URL (linking to doi.org/DOI)
                doi_url = "https://doi.org/" + related_doi_check
                assert url_loc == doi_url
                # Check the expected text of the related table DOI tag
                assert url_tag.text == f"Test Table {test['expected_number']}"
                # Check the expected title of the related table DOI tag
                assert url_tag.get_attribute('title') == f"Test Description {test['expected_number']}"

def test_version_related_table(live_server, logged_in_browser):
    """
    Tests the related table data on the records page.
    Checks that the tooltip and description are correct.
    """
    browser = logged_in_browser
    browser.file_detector = LocalFileDetector()
    record = {'title': "Test Title",
                  'reviewer': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'uploader': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'message': 'This is ready',
                  'user_id': 1}
    """
        Test data and the expected test outcomes
        Expected data is only checked on the second version
        Each version relates to both version 1 and 2 of the other submission
    """
    test_data = [
        {
            "title": "Submission1",
            "recid" : None,
            "other_recid": None,
            "inspire_id": 1,
            "versions": [
                {
                    "version": 1,
                    "submission" : None,
                    "directory": "test_data/test_version/test_1_version_1"
                },
                {
                    "version" : 2,
                    "submission" : None,
                    "directory": "test_data/test_version/test_1_version_2",
                    "related_to_expected": [{
                        "url_text": "TestTable2-V1",
                        "url_title": "TestTable2-description-V1"
                    },
                    {
                        "url_text": "TestTable2-V2",
                        "url_title": "TestTable2-description-V2"
                    }],
                    "related_to_this_expected": "TestTable2-V2"
                }
            ]
        },
        {
            "title": "Submission2",
            "recid": None,
            "other_recid" : None,
            "inspire_id": 25,
            "versions": [
                {
                    "version": 1,
                    "submission": None,
                    "directory": "test_data/test_version/test_2_version_1"
                },
                {
                    "version": 2,
                    "submission": None,
                    "directory": "test_data/test_version/test_2_version_2",
                    "related_to_expected": [
                    {
                        "url_text": "TestTable1-V1",
                        "url_title": "TestTable1-description-V1"
                    },
                    {
                        "url_text": "TestTable1-V2",
                        "url_title": "TestTable1-description-V2"
                    }],
                    "related_to_this_expected": "TestTable1-V2"
                }
            ]
        }
    ]

    # Insert the data
    for test in test_data:
        for version in test["versions"]:
            # Version 1 needs a different submission setup to v2
            if version["version"] == 1:
                version["submission"] = process_submission_payload(**record)
                version["submission"].overall_status = "finished"
                test["recid"] = version["submission"].publication_recid
            else:
                # Creates a new version of the submission and inserts it.
                version["submission"] = HEPSubmission(
                    publication_recid=test["recid"],
                    inspire_id=test["inspire_id"],
                    version=version["version"],
                    overall_status='finished')
                db.session.add(version["submission"])
                db.session.commit()

            # Fixes pathing when tests are ran together as it could not be figured out at the time
            if not os.path.exists(version["directory"]):
                version["directory"] = "tests/" + version["directory"]

            # Insertion of data, this is done for both versions
            data_dir = get_data_path_for_record(test["recid"], str(int(round(time.time())+version["version"])) )
            shutil.copytree(os.path.abspath(version["directory"]), data_dir)
            process_submission_directory(
                data_dir,
                os.path.join(data_dir, 'submission.yaml'),
                test["recid"]
            )

    # Set the expected recids for the test data
    test_data[0]["other_recid"] = test_data[1]["recid"]
    test_data[1]["other_recid"] = test_data[0]["recid"]

    # Insert related data dynamically to ensure the ids are correct
    # Ids differ when ran alongside other tests due to the test database having extra submissions
    for test in test_data:
        for v in test["versions"]:
            sub = v["submission"]
            related_recid = RelatedRecid(this_recid=test["recid"], related_recid=test["other_recid"])
            related_table_one = RelatedTable(table_doi=f"10.17182/hepdata.{test['recid']}.v1/t1", related_doi=f"10.17182/hepdata.{test['other_recid']}.v1/t1")
            related_table_two = RelatedTable(table_doi=f"10.17182/hepdata.{test['recid']}.v2/t1", related_doi=f"10.17182/hepdata.{test['other_recid']}.v2/t1")
            sub.related_recids.append(related_recid)
            datasub = DataSubmission.query.filter_by(doi=f"10.17182/hepdata.{test['recid']}.v{v['version']}/t1").first()
            datasub.related_tables.append(related_table_one)
            datasub.related_tables.append(related_table_two)
            db.session.add_all([related_recid, related_table_one, related_table_two])
            db.session.commit()

    # The checks
    for test in test_data:
        # We only need to use one submission version from each record for testing, so we're using the most recent
        version = test["versions"][1]
        record_url = flask.url_for('hepdata_records.get_metadata_by_alternative_id',
                                   recid=version["submission"].publication_recid, _external=True)
        browser.get(record_url)
        related_area = browser.find_element(By.ID, "related-tables")
        # Get the related data list html based on the current element
        data_list = (related_area.find_element(By.CLASS_NAME, "related-list-container")
                     .find_element(By.CLASS_NAME, "related-list")
                     .find_elements(By.TAG_NAME, "li"))
        for d in data_list:
            tag = d.find_element(By.TAG_NAME, "a")
            # Set the found attributes and check against the expected data
            data = { "url_text" : tag.text, "url_title": tag.get_attribute("title")}
            assert data in version["related_to_expected"]

        # Related to this
        related_to_this_area = browser.find_element(By.ID, "related-to-this-tables")
        related_to_this_list = (related_to_this_area.find_element(By.CLASS_NAME, "related-list-container")
                                .find_element(By.CLASS_NAME, "related-list")
                                .find_elements(By.TAG_NAME, "li"))
        assert len(related_to_this_list) == 1
        assert related_to_this_list[0].text == version["related_to_this_expected"]


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

    # Assuming you run this with TestHEPSubmission.zip
    # Collect text of all a tags found within the resource-items
    resource_elements = browser.find_elements(By.CLASS_NAME, "resource-item")
    links = [x.text for e in resource_elements for x in e.find_elements(By.TAG_NAME, "a")]
    # Check to see if the license text appears within
    assert "GPL2" not in links

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


def test_large_file_load(app, live_server, admin_idx, logged_in_browser):
    """
    Tests the loading of a large (over 1mb) file to the database.
    Used for testing the load button on the records page that appears when a file is
    too large for immediate loading.
    """
    browser = logged_in_browser
    with app.app_context():
        admin_idx.recreate_index()

        # Create the test record
        submission = create_test_record(os.path.abspath("tests/test_data/TestLargeSubmission"))
        # Load the webpage
        record_url = flask.url_for('hepdata_records.get_metadata_by_alternative_id',
                                   recid=submission.publication_recid, _external=True)
        browser.get(record_url)

        # The required elements for testing/navigation
        table_name = browser.find_element(By.ID, "table_name")
        table_description = browser.find_element(By.ID, "table_description")
        load_button = browser.find_element(By.ID, "hepdata_filesize_loading_button")
        data_table = browser.find_element(By.ID, "hep_table")
        tables = browser.find_element(By.ID, "table-list").find_elements(By.TAG_NAME, "li")

        # Wait for the table to attempt to load
        WebDriverWait(browser, 15).until(
            EC.visibility_of(table_name)
        )
        # Check the contents of the top table data
        assert table_name.text == "Table 1"
        assert table_description.text == "Test Table 1"
        # Check that the filesize error message and size has displayed
        pattern = r"The table size is (\d+(\.\d+)?) MB, which is greater than our threshold of (\d+(\.\d+)?) MB."
        assert re.match(
            pattern,
            browser.find_element(By.ID, "filesize_table_size").text
        )
        # Check for load button/contents
        assert EC.visibility_of(load_button)
        assert EC.visibility_of(browser.find_element(By.ID, "hepdata_filesize_loader"))

        # Click to load the table
        load_button.click()
        # Check that the animation is now visible and wait for loading
        assert EC.visibility_of(browser.find_element(By.ID, "filesize_table_loading"))
        WebDriverWait(browser, 15).until(
            EC.visibility_of(data_table)
        )

        # Swap to a new table and wait (this one is under the size)
        tables[1].click()
        WebDriverWait(browser, 15).until(
            EC.visibility_of(data_table)
        )

        # Check that the table is now visible
        assert table_name.text == "Table 2"
        assert table_description.text == "Test Table 2"
        assert EC.visibility_of(data_table)

        # Test the uploaded resources
        # Just checking against the existence of the element.
        for resource, expected in zip(submission.resources, ["code-contents-fail", "code-contents"]):
            web_url = flask.url_for(
                'hepdata_records.get_resource',
                resource_id=resource.id, landing_page=True,
                _external=True)
            browser.get(web_url)
            assert EC.visibility_of(expected)

def test_logged_out_observer(app, live_server, admin_idx, env_browser):
    """
    Testing that a logged out browser is not able to access an unfinished submission, and that
    the browser can also access a submission through its resource ID.
    """

    logged_out_browser = env_browser

    with app.app_context():
        test_submission = create_test_record(
            os.path.abspath('tests/test_data/test_submission'),
            overall_status='todo'
        )

        test_submission_observer = SubmissionObserver.query.filter_by(
            publication_recid=test_submission.publication_recid).first()

        record_url = flask.url_for('hepdata_records.get_metadata_by_alternative_id',
                                   recid=test_submission.publication_recid, _external=True)
    observer_append = f"?observer_key=%s"

    for test_key in [None, "BAD_KEY1"]:
        bad_url = record_url

        if test_key:
            bad_url += observer_append % test_key

        logged_out_browser.get(bad_url)
        form_exists = logged_out_browser.find_element(By.TAG_NAME, 'form')
        assert 'Log In' in form_exists.text

    observer_url = record_url + observer_append % test_submission_observer.observer_key
    logged_out_browser.get(observer_url)
    submission_title = logged_out_browser.find_element(By.CLASS_NAME, 'record-title').text

    assert submission_title == "HEPData Testing"

    json_link = logged_out_browser.find_element(By.ID, 'json_link').get_attribute('href')
    test_url = flask.url_for('converter.download_data_table_by_recid',
                             recid=test_submission.publication_recid,
                             table_name="Table 1",
                             version=test_submission.version,
                             file_format='json',
                             _external=True)

    json_url = test_url + observer_append % test_submission_observer.observer_key

    assert json_link == json_url
