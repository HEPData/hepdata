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

"""HEPData importer test cases."""
import datetime
import logging

import requests
import requests_mock

from hepdata.modules.records.importer.api import get_inspire_ids


def test_get_inspire_ids(caplog):
    caplog.set_level(logging.ERROR)
    dummy_ids = list(range(5))

    # Use requests_mock to mock the responses from hepdata.net.
    # Setting complete_qs=True means the mocker will only respond
    # if the entire URL including query string is correct
    with requests_mock.Mocker() as mock:
        # Test basic call just returns the ids directly from the response
        mock.get('https://hepdata.net/search/ids?inspire_ids=true',
                 json=dummy_ids, complete_qs=True)
        ids = get_inspire_ids()
        assert ids == dummy_ids

        # Test last_updated is passed correctly to URL
        mock.get('https://hepdata.net/search/ids?inspire_ids=true&last_updated=2019-12-31',
                 json=dummy_ids, complete_qs=True)
        ids = get_inspire_ids(last_updated=datetime.date(2019, 12, 31))
        assert ids == dummy_ids

        # Test limiting number of responses uses sort_by and restricts the results
        # returned
        mock.get('https://hepdata.net/search/ids?inspire_ids=true&sort_by=latest',
                 json=dummy_ids, complete_qs=True)
        ids = get_inspire_ids(n_latest=2)
        assert ids == dummy_ids[:2]

        # Test 404 response
        mock.get('https://hepdata.net/search/ids?inspire_ids=true',
                 complete_qs=True, status_code=404)
        ids = get_inspire_ids()
        assert ids is False
        assert len(caplog.records) == 2
        assert all([r.levelname == "ERROR" for r in caplog.records])
        assert caplog.records[0].msg == \
            "Unable to retrieve data from https://hepdata.net/search/ids?inspire_ids=true: 404 Not Found"
        assert caplog.records[1].msg == "Aborting."

        # Test connection error response
        caplog.clear()
        mock.get('https://hepdata.net/search/ids?inspire_ids=true',
                 complete_qs=True, exc=requests.exceptions.ConnectTimeout("mock error message"))
        ids = get_inspire_ids()
        assert ids is False
        assert len(caplog.records) == 3
        assert all([r.levelname == "ERROR" for r in caplog.records])
        assert caplog.records[0].msg == \
            "Unable to retrieve data from https://hepdata.net/search/ids?inspire_ids=true: "
        assert caplog.records[1].msg == "Socket error: mock error message."
        assert caplog.records[2].msg == "Aborting."

        # Test bad data response (not json)
        caplog.clear()
        mock.get('https://hepdata.net/search/ids?inspire_ids=true',
                 text="this is not valid json", complete_qs=True)
        ids = get_inspire_ids()
        assert ids is False
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert caplog.records[0].msg == \
            "Unexpected response from https://hepdata.net/search/ids?inspire_ids=true: this is not valid json"

        # Test bad data response (not iterable)
        caplog.clear()
        mock.get('https://hepdata.net/search/ids?inspire_ids=true',
                 json=3, complete_qs=True)
        ids = get_inspire_ids()
        assert ids is False
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert caplog.records[0].msg == \
            "Unexpected response from https://hepdata.net/search/ids?inspire_ids=true: 3"
