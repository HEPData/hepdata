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

"""HEPData Converter."""

import contextlib
import tempfile
import zipfile
from shutil import rmtree

from shutil import move

from flask import current_app
from hepdata_converter_ws_client import convert

from hepdata.config import CFG_CONVERTER_URL, CFG_CONVERTER_TIMEOUT
from hepdata.modules.records.utils.common import find_file_in_directory


def convert_zip_archive(input_archive, output_archive, options):
    """
    Convert a zip archive into a targz path with given options.

    :param input_archive:
    :param output_archive:
    :param options:
    :return: output_file
    """
    input = options.get('input_format', 'yaml')
    with prepare_data_folder(input_archive, input) as validation:
        if not validation:
            return None

        input_directory, input_file = validation

        successful = convert(
            current_app.config.get('CFG_CONVERTER_URL', CFG_CONVERTER_URL),
            input_directory if input == 'yaml' else input_file,
            output=output_archive,
            options=options,
            extract=False,
            timeout=CFG_CONVERTER_TIMEOUT,
        )

    # Error occurred, the output is a HTML file
    if not successful:
        output_file = output_archive[:-7] + '.html'
    else:
        output_file = output_archive
    move(output_archive, output_file)

    return output_file


def convert_oldhepdata_to_yaml(input_path, output_path):
    """
    Converts the data on the server from oldhepdata format to the new YAML format.

    :param input_path:
    :param output_path:
    :return: whether conversion was successful
    """
    options = {
        'input_format': 'oldhepdata',
        'output_format': 'yaml',
    }
    successful = convert(
        current_app.config.get('CFG_CONVERTER_URL', CFG_CONVERTER_URL),
        input_path,
        output=output_path,
        options=options,
        timeout=CFG_CONVERTER_TIMEOUT,
    )

    return successful


@contextlib.contextmanager
def prepare_data_folder(input_archive, input_format):
    input_root_dir = tempfile.mkdtemp(dir=current_app.config['CFG_TMPDIR'])
    try:
        with zipfile.ZipFile(input_archive, 'r') as zip_archive:
            zip_archive.extractall(path=input_root_dir)

        # Find the appropriate file/directory in the input archive
        yield find_file_in_directory(
            input_root_dir,
            lambda x: x == 'submission.yaml' if input_format == 'yaml' else x.endswith('.oldhepdata')
        )
    finally:
        rmtree(input_root_dir)
