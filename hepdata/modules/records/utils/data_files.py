# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
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
import hashlib
import os

from flask import current_app


def find_submission_data_file_path(submission):
    """Find the data file path for a submission. Looks in both old
    and new directory patterns."""
    # Try old location as well as new, so downloads still work whilst files
    # are being migrated
    data_filename = current_app.config['SUBMISSION_FILE_NAME_PATTERN'] \
                               .format(submission.publication_recid,
                                       submission.version)

    path = get_data_path_for_record(str(submission.publication_recid),
                                    data_filename)

    if not os.path.isfile(path):
        path = os.path.join(current_app.config['CFG_DATADIR'],
                            str(submission.publication_recid), data_filename)
    return path


def get_converted_directory_path(record_id):
    """Return the path for converted files for the given record id"""
    return os.path.join(current_app.config['CFG_DATADIR'],
                        'converted',
                        get_subdir_name(record_id))


def get_data_path_for_record(record_id, *subpaths):
    """Return the path for data files for the given record id."""
    path = os.path.join(current_app.config['CFG_DATADIR'],
                        get_subdir_name(record_id),
                        record_id,
                        *subpaths)
    return path


def get_subdir_name(record_id):
    hash_object = hashlib.sha256(record_id.encode())
    hex_dig = hash_object.hexdigest()
    return str(hex_dig)[:2]
