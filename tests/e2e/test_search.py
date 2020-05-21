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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.e2e.conftest import make_screenshot
from time import sleep


def test_search_from_home(live_server, env_browser, search_tests):
    """Test search functionality"""
    browser = env_browser

    # Go to index page
    browser.get(flask.url_for('hepdata_theme.index', _external=True))
    assert (flask.url_for('hepdata_theme.index', _external=True) in
            browser.current_url)

    # Click 'View all'
    search_all_link = browser.find_element_by_css_selector('#latest_records_section').find_element_by_tag_name('a')
    search_all_link.click()
    element = WebDriverWait(browser, 10).until(
        EC.url_contains('search')
    )
    assert (flask.url_for('es_search.search', _external=True) in
            browser.current_url)

    # Check result count
    sleep(1)
    results = browser.find_elements_by_class_name('search-result-item')
    assert(len(results) == 2)

    # Check facet filtering for each facet
    facets = [
        {'class_prefix': 'collaboration', 'exp_filter_count': 2, 'exp_first_result_count': 1},
        {'class_prefix': 'subject_areas', 'exp_filter_count': 1, 'exp_first_result_count': 2},
        {'class_prefix': 'phrases', 'exp_filter_count': 10, 'exp_first_result_count': 1},
        {'class_prefix': 'reactions', 'exp_filter_count': 9, 'exp_first_result_count': 1},
        {'class_prefix': 'observables', 'exp_filter_count': 3, 'exp_first_result_count': 1},
        {'class_prefix': 'cmenergies', 'exp_filter_count': 10, 'exp_first_result_count': None}
    ]

    for facet in facets:
        # Check the number of filters for the facet
        facet_filters = browser.find_elements_by_css_selector('#' + facet['class_prefix'] + '-facet li.list-group-item a')
        assert(len(facet_filters) == facet['exp_filter_count'])

        if len(facet_filters) > 0 and facet['exp_first_result_count'] is not None:
            # Check the number of results for first filter in the facet
            result_count = int(facet_filters[0].find_element_by_class_name('facet-count').text.strip())
            assert(result_count == facet['exp_first_result_count'])

            # Move to the first filter and click
            ActionChains(browser).move_to_element(facet_filters[0])
            facet_filters[0].click()
            assert (flask.url_for('es_search.search', _external=True) in
                    browser.current_url)

            # Check the number of search results matches the number given in the filter
            results = browser.find_elements_by_class_name('search-result-item')
            assert(len(results) == facet['exp_first_result_count'])

            # Go back to the previous search results
            browser.back()

    for search_config in search_tests:
        try:
            # Go to the homepage
            browser.get(flask.url_for('hepdata_theme.index', _external=True))
            assert (flask.url_for('hepdata_theme.index', _external=True) in
                    browser.current_url)

            # Find the search form, input the query and submit
            search_form = browser.find_element_by_class_name('main-search-form')
            search_input = search_form.find_element_by_name('q')

            search_term = search_config['search_term']
            search_input.send_keys(search_term)

            search_form.submit()
            sleep(1)

            assert (flask.url_for('es_search.search', _external=True) in
                    browser.current_url)

            # Check the expected publication appears in the search results
            publication = browser.find_element_by_class_name(search_config['exp_hepdata_id'])
            assert (publication)

            # Check the expected collaboration facets appear in the filters
            collab_facets = browser.find_element_by_css_selector('#collaboration-facet ul.list-group li.list-group-item a')
            assert(collab_facets.text.startswith(search_config['exp_collab_facet']))
            assert(collab_facets.text.endswith('1'))

            # Click on the link to the publication details
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
            print('Error occurred on test. Screenshot captured and saved in tmpdir as {}'.format(screenshot_name))
            raise e


def test_author_search(live_server, env_browser):
    """Test the author search"""
    browser = env_browser

    # Go to the search page
    browser.get(flask.url_for('es_search.search', _external=True))

    # Find the author search box
    search_input = browser.find_element_by_css_selector('#author-suggest')
    search_input.send_keys('ada')

    # Wait for search results to appear
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'tt-suggestion'))
    )

    # Check author results are as we expect
    search_results = browser.find_elements_by_class_name('tt-suggestion')
    expected_authors = [
        'Falkowski, Adam',
        'Lyon, Adam Leonard'
    ]

    assert(len(search_results) == len(expected_authors))

    for i, result in enumerate(search_results):
        assert(result.text == expected_authors[i])
