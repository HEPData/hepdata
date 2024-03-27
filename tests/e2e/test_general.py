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

"""HEPData end to end testing of general pages."""
import flask
import requests
import zipfile
import io

from invenio_db import db
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tests.conftest import import_default_data

from hepdata.ext.opensearch.api import reindex_all
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.submission import unload_submission


def test_home(app, live_server, env_browser, e2e_identifiers):
    """E2E home test to check record counts and latest submissions."""
    browser = env_browser

    # 1a. go to the home page
    browser.get(flask.url_for('hepdata_theme.index', _external=True))
    assert (flask.url_for('hepdata_theme.index', _external=True) in
            browser.current_url)

    # 2. check number of records and the number of datatables is correct
    record_stats = browser.find_element(By.CSS_SELECTOR, "#record_stats")
    exp_data_table_count = sum([i['data_tables'] for i in e2e_identifiers])
    exp_publication_count = len(e2e_identifiers)
    assert (record_stats.text == "Search on {0} publications and {1} data tables."
            .format(exp_publication_count, exp_data_table_count))

    # 3. check that there are three submissions in the latest submissions section
    assert len(browser.find_elements(By.CSS_SELECTOR, '.latest-record .title')) == 3
    # 4. click on the third submission (should be one in e2e_identifiers)
    third_item = browser.find_elements(By.CSS_SELECTOR, '.latest-record .title')[2]
    actions = ActionChains(browser)
    actions.move_to_element(third_item).perform()
    href = third_item.get_attribute("href")
    hepdata_id = href[href.rfind("/")+1:]
    third_item.click()

    # 5. assert that the submission is what we expected it to be.

    assert (flask.url_for('hepdata_records.get_metadata_by_alternative_id', recid=hepdata_id, _external=True) in
            browser.current_url)

    assert (browser.find_element(By.CSS_SELECTOR, '.record-title').text is not None)
    assert (browser.find_element(By.CSS_SELECTOR, '.record-journal').text is not None)
    assert (browser.find_element(By.CSS_SELECTOR, '#table-list-section li') is not None)

    table_placeholder = browser.find_element(By.CSS_SELECTOR, '#table-filter').get_attribute('placeholder')
    expected_record = [x for x in e2e_identifiers if x['hepdata_id'] == hepdata_id]
    assert (table_placeholder == "Filter {0} data tables".format(expected_record[0]['data_tables']))

    # Check file download works
    browser.find_element(By.ID, 'dLabel').click()
    download_original_link = browser.find_element(By.ID, 'download_original')
    download_url = download_original_link.get_attribute("href")
    assert(download_url.endswith("/download/submission/ins1283842/1/original"))
    # We can't test file downloads via selenium on SauceLabs so we'll just
    # download it using requests and check it's a valid zip
    response = requests.get(download_url)
    assert(response.status_code == 200)
    try:
        zipfile.ZipFile(io.BytesIO(response.content))
    except zipfile.BadZipFile:
        assert False, "File is not a valid zip file"
    # Close download dropdown by clicking again
    browser.find_element(By.ID, 'dLabel').click()

    # Go back to homepage and click on 1st link - should be record with resources
    browser.back()
    latest_item = browser.find_elements(By.CSS_SELECTOR, '.latest-record .title')[0]
    actions = ActionChains(browser)
    actions.move_to_element(latest_item).perform()
    latest_item.click()

    assert (flask.url_for('hepdata_records.get_metadata_by_alternative_id', recid='ins1883075', _external=True) in
            browser.current_url)
    # Check Resources button is present
    resources_btn = browser.find_element(By.ID, 'show_all_resources')
    assert resources_btn is not None
    resources_btn.click()

    # Wait until resource pane is visible
    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located((By.ID, 'resource-modal-contents'))
    )
    submission_resources = browser.find_elements(By.CLASS_NAME, 'resource-item-container')
    assert len(submission_resources) == 3

    # Find Python file resource
    python_resources = [e for e in submission_resources if e.find_element(By.TAG_NAME, 'h4').text == 'Python File']
    assert len(python_resources) == 1
    python_resource = python_resources[0]
    download_btns = [btn for btn in python_resource.find_elements(By.CSS_SELECTOR, 'a.btn-sm')]
    assert download_btns[1].text == 'Download'
    # Get landing page URL from download link and load
    browser.get(download_btns[0].get_attribute("href"))
    # Check landing page has appropriate elements
    header_h4 = browser.find_element(By.CSS_SELECTOR, ".hepdata_table_detail_header h4")
    assert header_h4.find_element(By.CLASS_NAME, "pull-left").text.strip() == \
        "cut_based_id.py"
    textarea = browser.find_element(By.ID, "code-contents")
    assert """import numpy as np
import math
import ROOT as rt""" in textarea.text


def test_tables(app, live_server, env_browser):
    """E2E test to tables in a record."""
    browser = env_browser

    # Import record with non-default table names
    import_default_data(app, [{'hepdata_id': 'ins1206352'}])

    try:
        browser.get(flask.url_for('hepdata_theme.index', _external=True))
        assert (flask.url_for('hepdata_theme.index', _external=True) in
                browser.current_url)

        latest_item = browser.find_element(By.CSS_SELECTOR, '.latest-record .title')
        actions = ActionChains(browser)
        actions.move_to_element(latest_item).perform()
        latest_item.click()

        # Check current table name
        assert(browser.find_element(By.ID, 'table_name').text == 'Figure 8 panel (a)')

        # Check switching tables works as expected
        new_table = browser.find_elements(By.CSS_SELECTOR, '#table-list li h4')[2]
        assert(new_table.text == "Figure 8 panel (c)")
        new_table.click()
        _check_table_links(browser, "Figure 8 panel (c)")

        # Get link to table from table page
        table_link = browser.find_element(By.CSS_SELECTOR, '#data_link_container button') \
            .get_attribute('data-clipboard-text')
        assert(table_link.endswith('table=Figure%208%20panel%20(c)'))
        _check_table_links(browser, "Figure 8 panel (c)", url=table_link)

        # Check a link to a table name with spaces removed
        short_table_link = table_link.replace('%20', '')
        _check_table_links(browser, "Figure 8 panel (c)", url=short_table_link)

        # Check a link to an invalid table
        invalid_table_link = table_link.replace('Figure%208%20panel%20(c)', 'NotARealTable')
        _check_table_links(browser, "Figure 8 panel (a)", url=invalid_table_link)

    finally:
        # Delete record and reindex so added record doesn't affect other tests
        submission = get_latest_hepsubmission(inspire_id='1206352')
        unload_submission(submission.publication_recid)
        reindex_all(recreate=True)


def _check_table_links(browser, table_full_name, url=None):
    if url:
        # Replace port in url (5555 used for unit testing is set in pytest.ini not config
        url = url.replace('5000', '5555')
        # Check link works
        browser.get(url)

    # Wait until new table is loaded
    WebDriverWait(browser, 10).until(
        EC.text_to_be_present_in_element((By.ID, 'table_name'), table_full_name)
    )
    # Check download YAML link for table
    yaml_link = browser.find_element(By.ID, 'download_yaml_data') \
        .get_attribute('href')
    assert(yaml_link.endswith(f'/{table_full_name.replace(" ", "%20")}/1/yaml'))
    # Download yaml using requests and check we get expected filename
    filename_table = table_full_name.replace(' ', '_')
    response = requests.get(yaml_link)
    assert(response.status_code == 200)
    assert(response.headers['Content-Disposition']
           == f'attachment; filename="HEPData-ins1206352-v1-{filename_table}.yaml"')


def test_general_pages(live_server, env_browser):
    """Test general pages can be loaded without errors"""
    browser = env_browser

    browser.get(flask.url_for('hepdata_theme.about', _external=True))
    assert (flask.url_for('hepdata_theme.about', _external=True) in
            browser.current_url)

    browser.get(flask.url_for('hepdata_theme.submission_help', _external=True))
    assert (flask.url_for('hepdata_theme.submission_help', _external=True) in
            browser.current_url)

    browser.get(flask.url_for('hepdata_theme.terms', _external=True))
    assert (flask.url_for('hepdata_theme.terms', _external=True) in
            browser.current_url)

    browser.get(flask.url_for('hepdata_theme.cookie_policy', _external=True))
    assert (flask.url_for('hepdata_theme.cookie_policy', _external=True) in
            browser.current_url)


def test_accept_headers(app, live_server, e2e_identifiers):
    """Test records pages respond to Accept headers"""
    # Main submission page (using inspire_id)
    record_url = flask.url_for(
        'hepdata_records.get_metadata_by_alternative_id',
        recid=e2e_identifiers[0]["hepdata_id"],
        _external=True
    )
    response = requests.get(record_url, headers={'Accept': 'application/ld+json'})
    assert response.status_code == 200
    json_ld = response.json()
    # Check some fields to make sure it's json for right record
    assert json_ld['@id'] == 'https://doi.org/10.17182/hepdata.1'
    assert json_ld['url'] == 'http://localhost:5000/record/ins1283842?version=1'
    assert json_ld['@type'] == 'Dataset'

    # Main submission page (using rec id, and testing 'application/vnd.hepdata.ld+json')
    record_url = flask.url_for(
        'hepdata_records.metadata',
        recid=1,
        _external=True
    )
    response = requests.get(record_url, headers={'Accept': 'application/vnd.hepdata.ld+json'})
    assert response.status_code == 200
    json_ld2 = response.json()
    # Should be the same as before
    assert json_ld2 == json_ld

    # Data submission landing page
    record_url = flask.url_for(
        'hepdata_records.metadata',
        recid=2,
        _external=True
    )
    response = requests.get(record_url, headers={'Accept': 'application/ld+json'})
    assert response.status_code == 200
    json_ld3 = response.json()
    # Check some fields to make sure it's json for right record
    assert json_ld3['@id'] == 'https://doi.org/10.17182/hepdata.1.v1/t1'
    assert json_ld3['url'] == 'http://localhost:5000/record/2'
    assert json_ld3['@type'] == 'Dataset'
    assert json_ld3['distribution'] == [
        {'@type': 'DataDownload', 'contentUrl': 'http://localhost:5000/download/table/1/root', 'description': 'ROOT file', 'encodingFormat': 'https://root.cern'},
        {'@type': 'DataDownload', 'contentUrl': 'http://localhost:5000/download/table/1/yaml', 'description': 'YAML file', 'encodingFormat': 'https://yaml.org'},
        {'@type': 'DataDownload', 'contentUrl': 'http://localhost:5000/download/table/1/csv', 'description': 'CSV file', 'encodingFormat': 'text/csv'},
        {'@type': 'DataDownload', 'contentUrl': 'http://localhost:5000/download/table/1/yoda', 'description': 'YODA file', 'encodingFormat': 'https://yoda.hepforge.org'}
    ]

    # Data resource landing page (use last submission, which has resources)
    submission = get_latest_hepsubmission(inspire_id=e2e_identifiers[-1]["inspire_id"])
    resource_url = flask.url_for(
        'hepdata_records.get_resource',
        resource_id=submission.resources[0].id,
        _external=True
    ) + '?landing_page=true'
    response = requests.get(resource_url, headers={'Accept': 'application/ld+json'})
    assert response.status_code == 200
    json_ld4 = response.json()
    # Check some fields to make sure it's json for right record
    assert json_ld4['@id'] == 'https://doi.org/10.17182/hepdata.124.v1/r1'
    assert json_ld4['url'] == 'http://localhost:5000/record/resource/262?landing_page=true'
    assert json_ld4['@type'] == 'CreativeWork'
    assert json_ld4['contentUrl'] == 'http://localhost:5000/record/resource/262?view=true'

    # JSON-LD for submission without DOI
    submission.doi = ''
    db.session.add(submission)
    db.session.commit()
    record_url = flask.url_for(
        'hepdata_records.get_metadata_by_alternative_id',
        recid=e2e_identifiers[-1]["hepdata_id"],
        _external=True
    )
    response = requests.get(record_url, headers={'Accept': 'application/ld+json'})
    assert response.status_code == 404
    json_ld5 = response.json()
    assert json_ld5 == {
        'error': 'JSON-LD is unavailable for this record; JSON-LD is only available for finalised records with DOIs.'
    }

    # Test getting python resource directly via content negotiation
    response = requests.get(resource_url, headers={'Accept': 'text/x-python'})
    assert response.status_code == 200
    assert response.headers.get('Content-Disposition') == 'attachment; filename=cut_based_id.py'
    assert response.headers.get('Content-Type') == 'text/x-python; charset=utf-8'
    assert """import numpy as np
import math
import ROOT as rt""" in response.text

    # Test sending incorrect accept header
    response = requests.get(resource_url, headers={'Accept': 'application/x-tar'})
    assert response.status_code == 406
    assert response.json() == {
        "file_mimetype": "text/x-python",
        "msg": "Accept header value 'application/x-tar' does not contain a valid media type for this resource. Expected Accept header to include one of 'text/x-python', 'text/html', 'application/ld+json', 'application/vnd.hepdata.ld+json'"
    }
