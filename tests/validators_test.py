# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2020 CERN.
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

import pytest
import requests_mock

from hepdata_validator.full_submission_validator import FullSubmissionValidator

import hepdata.modules.records.utils.validators
from hepdata.modules.records.utils.validators import get_full_submission_validator


def test_get_validator_initial():
    """
    Checks that a FullSubmissionValidator object is returned
    and populated to the global cached of the `validators` modules
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None

    validator = get_full_submission_validator(use_old_schema=False)

    assert type(validator) == FullSubmissionValidator
    assert hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR is validator


def test_get_validator_cached():
    """
    Checks that once a FullSubmissionValidator object has been cached,
    the same object is returned on successive calls
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None

    initial_validator = get_full_submission_validator(use_old_schema=False)

    # Successive calls that should returned the cached validator
    cached_validator_1 = get_full_submission_validator(use_old_schema=False)
    cached_validator_2 = get_full_submission_validator(use_old_schema=False)

    assert cached_validator_1 is initial_validator
    assert cached_validator_2 is initial_validator


def test_load_remote_schemas_valid():
    """
    Checks that loading of remote schemas when there is
    a valid response from the remote server
    N.B. This is now testing functionality from hepdata-validator,
    but leaving it in to prove backwards-compatibility
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None

    accepted_schemas = hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS

    # Set up a valid list of validation schemas
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = [
        {
            'base_url': 'https://scikit-hep.org/pyhf/schemas/1.0.0/',
            'schemas': ['model.json'],
        },
    ]

    schema_name = 'https://scikit-hep.org/pyhf/schemas/1.0.0/model.json'

    validator = get_full_submission_validator()

    assert validator._data_file_validator.custom_data_schemas != {}
    assert validator._data_file_validator.custom_data_schemas[schema_name] is not None

    # Reset ACCEPTED_REMOTE_SCHEMAS and CACHED_FULL_VALIDATOR
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = accepted_schemas
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None


def test_load_remote_schemas_invalid():
    """
    Checks that loading of remote schemas when there is
    an invalid response from the remote server
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None

    accepted_schemas = hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS

    # Set up a valid list of validation schemas
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = [
        {
            'base_url': 'https://random-org.com/project/schemas/1.0.0/',
            'schemas': ['not-found.json'],
        },
    ]

    # Use requests_mock to ensure requests gives a 404
    with requests_mock.Mocker() as m:
        m.register_uri('GET', 'https://random-org.com/project/schemas/1.0.0/not-found.json', text='Not Found', status_code=404)
        with pytest.raises(FileNotFoundError):
            get_full_submission_validator()

        assert m.called

    # Reset ACCEPTED_REMOTE_SCHEMAS and CACHED_FULL_VALIDATOR
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = accepted_schemas
    hepdata.modules.records.utils.validators.CACHED_FULL_VALIDATOR = None
