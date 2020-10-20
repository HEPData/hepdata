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
import logging
import os

from hepdata.modules.records.utils.data_files import get_data_path_for_record

logging.basicConfig()
log = logging.getLogger(__name__)


def download_resource_file(recid, resource_path):
    """
    :param inspire_id:
    :return:
    """
    base_url = "http://hepdata.cedar.ac.uk/{}"

    output_location = os.path.join(get_data_path_for_record(str(recid)), 'resources')

    if not os.path.exists(output_location):
        os.makedirs(output_location)

    from urllib.request import urlopen

    url = resource_path
    if 'resource' in resource_path:
        url = base_url.format(resource_path)

    response = urlopen(url)
    contents = response.read()
    # save to tmp file

    file_parts = resource_path.split('/')
    file_name = file_parts[-1]

    # this should only happen when a directory is referenced,
    # in which case it's a HTML file.
    if file_name == "":
        file_name = "index.html"

    with open(os.path.join(output_location, file_name), 'wb+') as resource_file:
        try:
            resource_file.write(contents)
        except IOError as ioe:
            log.error("IO Error occurred when getting {0} to store in {1}".format(resource_path, output_location))

    return os.path.join(output_location, file_name)
