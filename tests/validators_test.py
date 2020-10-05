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
import hepdata.modules.records.utils.validators

from hepdata.modules.records.utils.validators import DataFileValidator
from hepdata.modules.records.utils.validators import get_data_validator
from hepdata.modules.records.utils.validators import load_remote_schemas


def test_get_data_validator_initial():
    """
    Checks that a DataValidator object is returned
    and populated to the global cached of the `validators` modules
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_DATA_VALIDATOR = None

    data_validator = get_data_validator(old_hepdata=False)

    assert type(data_validator) == DataFileValidator
    assert hepdata.modules.records.utils.validators.CACHED_DATA_VALIDATOR is data_validator


def test_get_data_validator_cached():
    """
    Checks that once a DataValidator object has been cached,
    the same object is returned on successive calls
    """

    # Reset validator cache
    hepdata.modules.records.utils.validators.CACHED_DATA_VALIDATOR = None

    initial_validator = get_data_validator(old_hepdata=False)

    # Successive calls that should returned the cached validator
    cached_validator_1 = get_data_validator(old_hepdata=False)
    cached_validator_2 = get_data_validator(old_hepdata=False)

    assert cached_validator_1 is initial_validator
    assert cached_validator_2 is initial_validator


def test_load_remote_schemas_valid():
    """
    Checks that loading of remote schemas when there is
    a valid response from the remote server
    """

    # Set up a valid list of validation schemas
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = [
        {
            'base_url': 'https://scikit-hep.org/pyhf/schemas/1.0.0/',
            'schemas': ['model.json'],
        },
    ]

    schema_name = 'https://scikit-hep.org/pyhf/schemas/1.0.0/model.json'

    data_validator = DataFileValidator()
    load_remote_schemas(data_validator)

    assert data_validator.custom_data_schemas != {}
    assert data_validator.custom_data_schemas[schema_name] is not None


def test_load_remote_schemas_invalid():
    """
    Checks that loading of remote schemas when there is
    an invalid response from the remote server
    """

    # Set up a valid list of validation schemas
    hepdata.modules.records.utils.validators.ACCEPTED_REMOTE_SCHEMAS = [
        {
            'base_url': 'https://random-org.com/project/schemas/1.0.0/',
            'schemas': ['not-found.json'],
        },
    ]

    data_validator = DataFileValidator()

    with pytest.raises(FileNotFoundError):
        load_remote_schemas(data_validator)
