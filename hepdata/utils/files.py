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

import fs
import io
import subprocess

from flask import current_app
from fs.opener import fsopen
from shutil import rmtree


def copy_file(src_file, dst_file, buffer_size=io.DEFAULT_BUFFER_SIZE):
    next_chunk = src_file.read(buffer_size)
    while next_chunk:
        dst_file.write(next_chunk)
        next_chunk = src_file.read(buffer_size)


def copy_files_or_directory(source_path, destination_path, delete_source=False):
    if current_app.config.get('PRODUCTION_MODE', False):
        copy_command = ['xrdcp', '-N', '-f']
    else:
        copy_command = ['cp']

    print('Copying with: {} -r {} {}'.format(' '.join(copy_command), source_path, destination_path))
    subprocess.check_output(
        copy_command + ['-r',  source_path, destination_path])

    if delete_source:
        rmtree(source_path, ignore_errors=True)


def ensure_xrootd_path(path):
    """Ensure xrootd path instead of local.

    You must enable ``EOS_ENABLE_XROOT = True`` otherwise will do nothing.
    """
    if not current_app.config.get('EOS_ENABLED', False):
        return path

    if path.startswith(current_app.config.get('CFG_TMPDIR', '')):
        return path

    if not path.startswith('root://'):
        path = path.replace(
            current_app.config['EOS_REPLACE_PREFIX'],
            current_app.config['EOS_DATADIR']
        )
    return path


def file_opener(path, mode='r'):
    """File opener.

    param path (str): the fullpath of the file
    param mode (str): mode to open file file
    """
    path = ensure_xrootd_path(path)
    return fsopen(path, mode=mode)
