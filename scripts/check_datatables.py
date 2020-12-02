#!/usr/bin/env python

from time import sleep

import click
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@click.group()
def cli():
    """This script checks whether data tables on hepdata.net can be loaded
    correctly. It uses Selenium WebDriver on chrome; please ensure you have
    installed Chrome and ChromeDriver before running this script.
    """


@cli.command()
@click.option('--start-page', '-s', default=1,
              help='The first page to check')
@click.option('--end-page', '-e', default=1,
              help='The last page to check (must be >= start-page)')
@click.option('--max-tables', '-m', default=5,
              help='Maximum number of data tables to check (-1 for all)')
@click.option('--username', '-u',
              help='HEPData username (email address) to log in '
              'to increase rate limits')
def check_by_page(start_page, end_page, max_tables, username):
    """Checks specified pages of search results (in the default order,
    i.e. latest first), clicks through to each submission, and loads each of
    the first max_table data tables in turn."""
    if end_page < start_page:
        click.echo("end-page must be greater than or equal to start-page")
        exit(1)

    password = None
    if username:
        password = click.prompt("Enter password for user %s:" % username,
                                hide_input=True)

    click.echo("Checking from page %s to %s of search results"
               % (start_page, end_page))

    driver = _get_driver(username, password)

    for page in range(int(start_page), int(end_page) + 1):
        click.echo("Checking page %s of search results" % page)
        driver.get('https://www.hepdata.net/search/?page=%s' % page)
        record_links = driver.find_elements_by_css_selector(
            '.search-result-item .record-header a'
        )
        urls = []

        for link in record_links:
            urls.append(link.get_attribute('href'))

        for url in urls:
            _check_url(url, max_tables, driver)


@cli.command()
@click.option('--url', '-u', type=str,
              help='URL to check for data tables')
@click.option('--max-tables', '-m', default=5,
              help='Maximum number of data tables to check (-1 for all)')
def check_url(url, max_tables):
    """Checks the given URL and loads each data table in turn, up
    to a maximum of max-tables tables."""
    driver = _get_driver()
    _check_url(url, max_tables, driver)


def _check_url(url, max_tables, driver):
    driver.get(url)
    table_links = driver.find_elements_by_css_selector('#table-list li')
    if max_tables > 0:
        table_links = table_links[:max_tables]

    for table_link in table_links:
        actions = ActionChains(driver)
        actions.move_to_element(table_link).perform()
        table_link.click()
        try:
            wait = WebDriverWait(driver, 20)
            wait.until(EC.visibility_of_element_located(
                (By.ID, "hepdata_table_content"))
            )
        except TimeoutException:
            click.echo("***** Missing table at %s: *****" % url)
            for el in driver.find_elements_by_id("hepdata_table_loading_failed"):
                click.echo("***** %s *****" % el.text)


def _get_driver(username=None, password=None):
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument('disable-infobars')
    driver = webdriver.Chrome(options=options,
                              executable_path=r'/usr/local/bin/chromedriver')
    driver.get('https://www.hepdata.net/search/')

    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_element_located(
        (By.CSS_SELECTOR, ".cc_btn_accept_all")
    ))
    sleep(1)
    cookie_accept_btn = driver.find_element_by_css_selector(".cc_btn_accept_all")
    cookie_accept_btn.click()

    if username and password:
        click.echo("Logging in...")
        driver.get('https://www.hepdata.net/login/')
        login_form = driver.find_element_by_name('login_user_form')
        login_form.find_element_by_name('email').send_keys(username)
        login_form.find_element_by_name('password').send_keys(password)
        login_form.submit()

    return driver


if __name__ == '__main__':
    cli()
