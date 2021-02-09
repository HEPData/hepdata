# This file is part of HEPData.
# Copyright (C) 2021 CERN.
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
import shutil
import time

from hepdata.modules.dashboard.views import do_finalise
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import \
    process_submission_directory, get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record

logging.basicConfig()
log = logging.getLogger(__name__)


def mock_import_old_record():
    """Creates a submission but mimics the old migrated paths. (See hepdata
    master branch at ccd691b for old migrator module.)
    """
    # Use zipped test data for specific record(s)
    inspire_id = '1299143'
    publication_information, status = get_inspire_record_information(inspire_id)
    publication_information["inspire_id"] = inspire_id

    # Create record
    if status == "success":
        record_information = create_record(publication_information)
    else:
        log.error("Failed to retrieve publication information for " + inspire_id)
        return False

    # Unzip into correct data dir
    data_path = get_data_path_for_record(record_information['recid'])
    base_dir = os.path.dirname(os.path.realpath(__file__))
    zip_path = os.path.join(base_dir, 'old_hepdata_zips', 'ins%s.zip' % inspire_id)
    if os.path.isfile(zip_path):
        log.info('Unzipping %s to %s' % (zip_path, data_path))
        shutil.unpack_archive(zip_path, data_path)
        time_stamp = str(int(round(time.time())))
        yaml_path = os.path.join(data_path, time_stamp)
        sub_zip_path = os.path.join(data_path, 'ins%s.zip' % inspire_id)
        shutil.unpack_archive(sub_zip_path, yaml_path)
    else:
        log.error('Invalid path %s' % zip_path)
        return False

    # Create submission
    admin_user_id = 1

    # Consume data payload and store in db.
    get_or_create_hepsubmission(record_information["recid"], admin_user_id)

    errors = process_submission_directory(yaml_path,
                                          os.path.join(yaml_path, "submission.yaml"),
                                          record_information["recid"],
                                          from_oldhepdata=True)

    if errors:
        log.error("Submission failed for {0}.".format(record_information["recid"]),
            errors,
            record_information["recid"])
        return False

    do_finalise(record_information['recid'], publication_record=record_information,
        force_finalise=True, convert=False)
