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

"""HEPData Converter Tasks."""

from celery import shared_task

from hepdata.modules.converter.views import download_submission
from hepdata.modules.submission.api import get_latest_hepsubmission

@shared_task
def convert_and_store(inspire_id, file_format, force):
    """
    Converts a submission to a given file format, and stores
    on the file system to be retrieved later by users.

    :param inspire_id:
    :param file_format:
    :param force:
    :return:
    """
    submission = get_latest_hepsubmission(inspire_id=inspire_id)
    if submission:
        print("Creating {0} conversion for ins{1}".format(file_format, inspire_id))
        download_submission(submission, file_format, offline=True, force=force)
    else:
        print("Unable to find a matching submission for {0}".format(inspire_id))
