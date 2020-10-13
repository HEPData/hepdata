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

import logging
import os

from hepdata_validator.data_file_validator import DataFileValidator
from hepdata_validator.schema_downloader import HTTPSchemaDownloader
from hepdata_validator.schema_resolver import JsonSchemaResolver
from hepdata_validator.submission_file_validator import SubmissionFileValidator

logging.basicConfig()
log = logging.getLogger(__name__)


# Expand list to add support
ACCEPTED_REMOTE_SCHEMAS = [
    {
        'base_url': 'https://scikit-hep.org/pyhf/schemas/1.0.0/',
        'schemas': [
            # The schemas need to be rendered by HEPData.
            # Containing fields: `independent_variables` and `dependent_variables`
            # Ref: https://github.com/HEPData/hepdata/pull/241#issuecomment-702389464
            #
            # None of the following pyhf schemas at v1.0.0 comply:
            # 'jsonpatch.json',
            # 'measurement.json',
            # 'model.json',
            # 'patchset.json',
            # 'workspace.json',
        ],
    },
]


# Define a global DataFileValidator object so that
# custom schemas are only loaded once
CACHED_DATA_VALIDATOR = None


def get_submission_validator():
    """
    Returns a SubmissionFileValidator object

    :return: SubmissionFileValidator object
    """

    return SubmissionFileValidator()


def get_data_validator(old_hepdata):
    """
    Returns a DataFileValidator object (with remote defined schemas loaded)

    :param old_hepdata: whether the schema version for the submission.yaml is 0.1.0
    :return: DataFileValidator object
    """

    global CACHED_DATA_VALIDATOR

    # Use for YAML files migrated from old HepData site
    if old_hepdata:
        data_validator = DataFileValidator(schema_version='0.1.0')

    elif CACHED_DATA_VALIDATOR:
        data_validator = CACHED_DATA_VALIDATOR

    else:
        data_validator = DataFileValidator()
        load_remote_schemas(data_validator)
        CACHED_DATA_VALIDATOR = data_validator

    return data_validator


def load_remote_schemas(data_validator):
    """
    Loads all the remotely-defined schemas in-place

    :param data_validator: DataFileValidator object to load schemas into
    :return: None
    """

    for org_schemas in ACCEPTED_REMOTE_SCHEMAS:
        schema_url = org_schemas['base_url']
        schema_names = org_schemas['schemas']

        resolver = JsonSchemaResolver(schema_url)
        downloader = HTTPSchemaDownloader(resolver, schema_url)

        # Retrieve and save the remote schema in the local path
        for name in schema_names:
            schema_type = downloader.get_schema_type(name)
            schema_spec = downloader.get_schema_spec(name)
            downloader.save_locally(name, schema_spec)

            # Load the custom schema as a custom type
            local_path = os.path.join(downloader.schemas_path, name)
            data_validator.load_custom_schema(schema_type, local_path)
