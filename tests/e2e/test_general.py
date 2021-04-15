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

from selenium.webdriver.common.action_chains import ActionChains
from functools import reduce


def test_home(live_server, env_browser, identifiers):
    """E2E home test to check record counts and latest submissions."""
    browser = env_browser
    # 1a. go to the home page
    browser.get(flask.url_for('hepdata_theme.index', _external=True))
    assert (flask.url_for('hepdata_theme.index', _external=True) in
            browser.current_url)

    # 2. check number of records and the number of datatables is correct
    record_stats = browser.find_element_by_css_selector("#record_stats")
    exp_data_table_count = reduce(lambda x, y: x['data_tables'] + y['data_tables'], identifiers)
    exp_publication_count = len(identifiers)
    assert (record_stats.text == "Search on {0} publications and {1} data tables."
            .format(exp_publication_count, exp_data_table_count))

    # 3. check that there are two submissions in the latest submissions section
    assert (browser.find_element_by_css_selector('.latest-record'))
    # 4. click on the first submission.
    latest_item = browser.find_element_by_css_selector('.latest-record .title')
    actions = ActionChains(browser)
    actions.move_to_element(latest_item).perform()
    browser.save_screenshot('/tmp/screenshot.png')
    href = latest_item.get_attribute("href")
    hepdata_id = href[href.rfind("/")+1:]
    latest_item.click()

    # 5. assert that the submission is what we expected it to be.

    assert (flask.url_for('hepdata_records.get_metadata_by_alternative_id', recid=hepdata_id, _external=True) in
            browser.current_url)

    assert (browser.find_element_by_css_selector('.record-title').text is not None)
    assert (browser.find_element_by_css_selector('.record-journal').text is not None)
    assert (browser.find_element_by_css_selector('#table-list-section li') is not None)

    table_placeholder = browser.find_element_by_css_selector('#table-filter').get_attribute('placeholder')
    expected_record = [x for x in identifiers if x['hepdata_id'] == hepdata_id]
    assert (table_placeholder == "Filter {0} data tables".format(expected_record[0]['data_tables']))

    # Check file download works
    browser.find_element_by_id('dLabel').click()
    download_original_link = browser.find_element_by_id('download_original')
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
