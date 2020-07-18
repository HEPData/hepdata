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


import tarfile
import zipfile
import gzip
import binascii

from hepdata.modules.records.utils.common import find_file_in_directory


def is_gz_file(filepath):
    # from https://stackoverflow.com/questions/3703276/how-to-tell-if-a-file-is-gzip-compressed
    with open(filepath, 'rb') as test_f:
        return binascii.hexlify(test_f.read(2)) == b'1f8b'


def extract(file_path, unzipped_path):
    if zipfile.is_zipfile(file_path):
        zipped_submission = zipfile.ZipFile(file_path)
        zipped_submission.printdir()
        zipped_submission.extractall(path=unzipped_path)
        zipped_submission.close()
        return unzipped_path
    elif tarfile.is_tarfile(file_path):
        tar = tarfile.open(file_path)
        tar.extractall(path=unzipped_path)
        tar.close()
        return unzipped_path
    elif is_gz_file(file_path):
        with gzip.GzipFile(file_path, 'rb') as gzip_file:
            with open(unzipped_path, 'wb') as unzipped_file:
                unzipped_file.write(gzip_file.read())
        return unzipped_path
    return None


def get_file_in_directory(path, extension):
    file_info = find_file_in_directory(path, lambda x: x.endswith(extension))
    return file_info[1] if file_info else None
