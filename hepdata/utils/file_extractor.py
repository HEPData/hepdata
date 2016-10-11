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

from hepdata.modules.records.utils.common import find_file_in_directory


def extract(file_name, file_path, unzipped_path):

    if file_name.endswith("tar.gz"):
        tar = tarfile.open(file_path, "r:gz")
        tar.extractall(path=unzipped_path)
        tar.close()
    elif file_name.endswith("tar"):
        tar = tarfile.open(file_path, "r:")
        tar.extractall(path=unzipped_path)
        tar.close()
    elif 'zip' in file_name:
        zipped_submission = zipfile.ZipFile(file_path)
        zipped_submission.printdir()

        zipped_submission.extractall(path=unzipped_path)

    return unzipped_path


def get_file_in_directory(path, extension):
    directory, file = find_file_in_directory(path, lambda x: x.endswith(extension))
    return file
