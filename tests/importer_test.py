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
import os
from unittest.mock import call

import requests
import requests_mock

from hepdata.modules.records.importer.api import get_inspire_ids, \
    _import_record, import_records
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission, DataSubmission


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


def test_import_record(app):
    all_submissions = HEPSubmission.query.all()
    assert len(all_submissions) == 0
    data_submissions = DataSubmission.query.all()
    assert len(data_submissions) == 0

    # Import a record and check it's been added to the db
    inspire_id = '1824424'
    result = _import_record(inspire_id)
    assert result is True

    all_submissions = HEPSubmission.query.all()
    assert len(all_submissions) == 1
    hep_submission = all_submissions[0]
    assert hep_submission.publication_recid == 1
    assert hep_submission.inspire_id == inspire_id
    assert hep_submission.overall_status == 'finished'
    last_updated = hep_submission.last_updated

    record = get_record_by_id(1)
    assert record['title'] == 'Measurement of the production cross section of 31 GeV/$c$ protons on carbon via beam attenuation in a 90-cm-long target'
    assert record['inspire_id'] == inspire_id
    assert record['abstract'].startswith('The production cross section of 30.92 GeV/$c$ protons on carbon is measured by')

    data_submissions = DataSubmission.query.all()
    assert len(data_submissions) == 2

    # Try the import again - should not update
    result = _import_record(inspire_id)
    assert result is False

    # Retry with update_existing=True
    result = _import_record(inspire_id, update_existing=True)
    assert result is True
    updated_submission = get_latest_hepsubmission(publication_recid=1)
    assert updated_submission.last_updated > last_updated

    # Try an old inspire id which uses the old schema
    old_inspire_id = '944937'
    result = _import_record(old_inspire_id)
    assert result is True
    all_submissions = HEPSubmission.query.all()
    assert len(all_submissions) == 2
    data_submissions = DataSubmission.query.all()
    assert len(data_submissions) == 3
    record = get_record_by_id(all_submissions[1].publication_recid)
    assert record['title'] == 'The Production of Charged Photomesons from Deuterium and Hydrogen. I'
    assert record['inspire_id'] == old_inspire_id
    assert record['abstract'].startswith('Hydrogen and deuterium gases have been bombarded in a gas target at a temperature of 77°K')

    # Try an invalid inspire id
    assert _import_record('thisisinvalid') is False

    # Mock errors with download
    with requests_mock.Mocker(real_http=True) as mock:
        # 404
        mock.get('https://hepdata.net/download/submission/ins{0}/original'.format(inspire_id),
                 status_code=404)
        result = _import_record(inspire_id, update_existing=True)
        assert result is False

        # Text not zip
        mock.get('https://hepdata.net/download/submission/ins{0}/original'.format(inspire_id),
                 text='This is not a zip')
        result = _import_record(inspire_id, update_existing=True)
        assert result is False

        # SocketError
        mock.get('https://hepdata.net/download/submission/ins{0}/original'.format(inspire_id),
                 exc=requests.exceptions.ConnectTimeout("mock error message"))
        result = _import_record(inspire_id, update_existing=True)
        assert result is False

        # Send an invalid zip
        base_dir = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(base_dir, 'test_data/submission_invalid_symlink.tgz')
        with open(file_path, 'rb') as f:
            mock.get('https://hepdata.net/download/submission/ins{0}/original'.format(inspire_id),
                     headers={'content-type': 'application/zip'}, body=f)
            result = _import_record(inspire_id, update_existing=True)
            assert result is False


def test_import_records(mocker):
    # Patch the _import_record function as it's tested elsewhere
    m = mocker.patch('hepdata.modules.records.importer.api._import_record')
    import_records(['ins12345', '67890'], synchronous=True)
    expected_args = [
        call('12345', base_url='https://hepdata.net', update_existing=False),
        call('67890', base_url='https://hepdata.net', update_existing=False),
    ]
    assert m.call_count == 2
    assert m.call_args_list == expected_args

    m.reset_mock()
    import_records(['ins54321'], base_url='https://localhost:5000',
                   update_existing=True, synchronous=True)
    m.assert_called_once_with('54321', base_url='https://localhost:5000',
                              update_existing=True)
