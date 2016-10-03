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

"""HEPData end to end testing of search."""
import flask
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.e2e.conftest import make_screenshot


def test_search_from_home(live_server, env_browser, search_tests):
    """E2E user registration and login test."""
    browser = env_browser

    for search_config in search_tests:
        try:
            browser.get(flask.url_for('hepdata_theme.index', _external=True))
            assert (flask.url_for('hepdata_theme.index', _external=True) in
                    browser.current_url)

            search_form = browser.find_element_by_class_name('main-search-form')
            search_input = search_form.find_element_by_name('q')

            search_term = search_config['search_term']
            search_input.send_keys(search_term)

            search_form.submit()

            assert (flask.url_for('es_search.search', _external=True) in
                    browser.current_url)

            publication = browser.find_element_by_class_name(search_config['exp_hepdata_id'])
            assert (publication)

            selector = ".{0} .record-header a".format(search_config['exp_hepdata_id'])

            element = WebDriverWait(browser, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            element.click()

            assert (flask.url_for('hepdata_records.get_metadata_by_alternative_id', recid=search_config['exp_hepdata_id'],
                                  _external=True) in browser.current_url)
        except Exception as e:
            screenshot_name = "./search-{}.png".format(search_config['exp_hepdata_id'])
            make_screenshot(browser, screenshot_name)
            print('Error occurred on test. Screenshot capured and saved in tmpdir as {}')
            raise e
