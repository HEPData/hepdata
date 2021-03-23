import os.path

import flask
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .conftest import e2e_assert_url


def test_sandbox(live_server, env_browser):
    browser = env_browser
    browser.file_detector = LocalFileDetector()

    # Log in
    browser.get(flask.url_for('security.login', _external=True))
    e2e_assert_url(browser, 'security.login')

    login_form = browser.find_element_by_name('login_user_form')
    login_form.find_element_by_name('email').send_keys('test@hepdata.net')
    login_form.find_element_by_name('password').send_keys('hello1')
    login_form.submit()

    # Go to sandbox
    sandbox_url = flask.url_for('hepdata_records.sandbox', _external=True)
    browser.get(sandbox_url)
    e2e_assert_url(browser, 'hepdata_records.sandbox')

    # Check there are no past sandbox submissions
    assert browser.find_element_by_id('past_submissions') \
        .find_elements_by_xpath(".//*") == []

    # Try uploading a file
    upload = browser.find_element_by_id('root_file_upload')
    ActionChains(browser).move_to_element(upload).perform()
    upload.send_keys(os.path.abspath("tests/test_data/TestHEPSubmission.zip"))
    browser.find_element_by_class_name('btn-primary').click()

    # Should redirect to record page with confirmation message
    WebDriverWait(browser, 10).until(
        EC.url_matches(f'{sandbox_url}/\\d+')
    )
    alert = browser.find_element_by_class_name('alert-info')
    assert alert.text == "File saved. You will receive an email when the file has been processed."

    # Record should have been processed immediately by test celery runner
    # so we can check its contents
    assert browser.find_element_by_class_name('record-abstract-content').text \
        .startswith('CERN-LHC.  Measurements of the cross section  for ZZ production')
    table_items = browser.find_element_by_id('table-list').find_elements_by_tag_name('li')
    assert len(table_items) == 8
    assert "active" in table_items[0].get_attribute("class")
    assert table_items[0].find_element_by_tag_name('h4').text == "Table 1"
    assert table_items[0].find_element_by_tag_name('p').text == "Data from Page 17 of preprint"
    table_content = browser.find_element_by_id('hepdata_table_content')
    assert table_content.find_element_by_id('table_name').text == "Table 1"
    assert table_content.find_element_by_id('table_location').text == "Data from Page 17 of preprint"

    # Check resources load (using button for table)
    # modal content should not be visible beforehand
    modal_content = browser.find_element_by_id('resourceModal')
    assert not modal_content.is_displayed()
    table_content.find_element_by_id('show_resources').click()
    WebDriverWait(browser, 10).until(
        EC.visibility_of(modal_content)
    )
    assert modal_content.find_element_by_id('additionalResource').text == \
        "Additional Publication Resources"
    assert modal_content.find_element_by_id('selected_resource_item').text == \
        "Table 1"

    resource_list_items = modal_content \
        .find_element_by_id('resource-list-items') \
        .find_elements_by_tag_name('li')

    # Check we can select a different table/common resources
    resource_list_items[0].click()
    assert modal_content.find_element_by_id('selected_resource_item').text == \
        "Common Resources"
    resource_list_items[8].click()
    assert modal_content.find_element_by_id('selected_resource_item').text == \
        "Table 8"

    # Check filtering by table name
    assert len([e for e in resource_list_items if e.is_displayed()]) == 9
    filter_field = modal_content.find_element_by_id('resource-filter-input')

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
    modal_content.find_element_by_class_name('close').click()
    WebDriverWait(browser, 10).until(
        EC.invisibility_of_element(modal_content)
    )

    # Try uploading another file
    browser.find_element_by_css_selector("button.btn-success[data-target='#uploadDialog']") \
        .click()
    upload_dialog = browser.find_element_by_id('uploadDialog')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(upload_dialog)
    )
    upload = upload_dialog.find_element_by_id('file_upload_field')
    ActionChains(browser).move_to_element(upload).perform()
    upload.send_keys(os.path.abspath("tests/test_data/sample.oldhepdata"))
    upload_dialog.find_element_by_css_selector('input[type=submit]').click()
    # Wait for page reload
    WebDriverWait(browser, 10).until(
        EC.staleness_of(upload_dialog)
    )
    alert = browser.find_element_by_class_name('alert-info')
    assert alert.text == "File saved. You will receive an email when the file has been processed."

    # Go back to the sandbox
    browser.get(sandbox_url)

    # Check that past submissions column now has a child
    past_submissions_div = browser.find_element_by_id('past_submissions')
    assert len(past_submissions_div.find_elements_by_class_name('col-md-10')) == 1

    # Delete the sandbox record
    past_submissions_div.find_element_by_class_name('delete_button').click()
    delete_modal = browser.find_element_by_id('deleteWidget')
    WebDriverWait(browser, 10).until(
        EC.visibility_of(delete_modal)
    )
    delete_modal.find_element_by_class_name('confirm-delete').click()
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element((By.ID, 'deleteDialogLabel'), 'Submission Deleted')
    )

    # Refresh sandbox page (to avoid waiting)
    browser.get(sandbox_url)

    # Check there are no past sandbox submissions
    assert browser.find_element_by_id('past_submissions') \
        .find_elements_by_xpath(".//*") == []
