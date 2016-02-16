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


def test_about(live_server, env_browser):
    """E2E user registration and login test."""
    browser = env_browser
    # 1. Go to user registration page
    browser.get(flask.url_for('hepdata_theme.about', _external=True))
    assert (flask.url_for('hepdata_theme.about', _external=True) in
            browser.current_url)


def test_submission_help(live_server, env_browser):
    """E2E user registration and login test."""
    browser = env_browser
    # 1. Go to user registration page
    browser.get(flask.url_for('hepdata_theme.submission_help', _external=True))
    assert (flask.url_for('hepdata_theme.submission_help', _external=True) in
            browser.current_url)
