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

"""records/utils/data_files test cases."""

import os

from hepdata.modules.records.utils.data_files import _get_subdir_name, \
    get_data_path_for_record, get_old_data_path_for_record, \
    get_converted_directory_path, find_submission_data_file_path
from hepdata.modules.submission.models import HEPSubmission


def test_get_subdir_name():
    assert(_get_subdir_name('mynewtestdir') == '17')
    assert(_get_subdir_name('ins12345') == '96')


def test_get_data_path_for_record(app):
    data_dir = app.config['CFG_DATADIR']
    assert(get_data_path_for_record('ins12345') == data_dir + '/96/ins12345')
    assert(get_data_path_for_record('ins12345', 'mysubdir', 'file.xyz')
           == data_dir + '/96/ins12345/mysubdir/file.xyz')


def test_get_old_data_path_for_record(app):
    data_dir = app.config['CFG_DATADIR']
    assert(get_old_data_path_for_record('ins12345') == data_dir + '/ins12345')
    assert(get_old_data_path_for_record('ins12345', 'mysubdir', 'file.xyz')
           == data_dir + '/ins12345/mysubdir/file.xyz')


def test_get_converted_directory_path(app):
    data_dir = app.config['CFG_DATADIR']
    assert(get_converted_directory_path('ins12345')
           == data_dir + '/converted/96')


def test_find_submission_data_file_path(app):
    data_dir = app.config['CFG_DATADIR']
    expected_file_name = 'HEPData-987654321-v2-yaml.zip'
    old_file_path = data_dir + '/987654321/' + expected_file_name
    new_file_path = data_dir + '/8a/987654321/' + expected_file_name
    # /8a/987654321/

    if os.path.exists(new_file_path):
        os.remove(new_file_path)

    # No new format file found, so should return old directory
    submission = HEPSubmission(publication_recid=987654321, version=2)
    assert(find_submission_data_file_path(submission)
           == old_file_path)

    # Create new file
    os.makedirs(data_dir + '/8a/987654321/', exist_ok=True)
    f = open(new_file_path, 'w')
    f.close()

    assert(find_submission_data_file_path(submission)
           == new_file_path)
