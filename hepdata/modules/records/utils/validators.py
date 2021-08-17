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

from hepdata_validator.full_submission_validator import FullSubmissionValidator

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


# Define a global FullSubmissionValidator object so that
# custom schemas are only loaded once
CACHED_FULL_VALIDATOR = None


def get_full_submission_validator(use_old_schema=False):
    """
    Returns a FullSubmissionValidator object

    :param old_schema: whether the schema version for the submission.yaml is 0.1.0
    :return: SubmissionFileValidator object
    """

    global CACHED_FULL_VALIDATOR

    # Use for YAML files migrated from old HepData site
    if use_old_schema:
        return FullSubmissionValidator(schema_version='0.1.0', autoload_remote_schemas=False)

    elif CACHED_FULL_VALIDATOR:
        validator = CACHED_FULL_VALIDATOR

    else:
        validator = FullSubmissionValidator(autoload_remote_schemas=False)
        for org_schemas in ACCEPTED_REMOTE_SCHEMAS:
            schema_url = org_schemas['base_url']
            schema_names = org_schemas['schemas']
            for name in schema_names:
                validator.load_remote_schema(base_url=schema_url, schema_name=name)

        CACHED_FULL_VALIDATOR = validator

    return validator
