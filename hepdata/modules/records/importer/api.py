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
import os
import requests
import shutil
import socket
import tempfile
import time

from celery import shared_task
from flask import current_app
from invenio_db import db

from hepdata.modules.dashboard.views import do_finalise
from hepdata.modules.records.api import process_zip_archive
from hepdata.modules.records.migrator.api import Migrator
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.api import get_latest_hepsubmission

logging.basicConfig()
log = logging.getLogger(__name__)


def import_records(inspire_ids, synchronous=True, base_url='https://hepdata.net'):
    """
    Import records from hepdata.net
    :param base_url: override default base URL
    :param synchronous: if should be run immediately
    :param inspire_ids: array of inspire ids to load (in the format insXXX).
    :return: None
    """
    for index, inspire_id in enumerate(inspire_ids):
        _cleaned_id = inspire_id.replace("ins", "")
        try:
            import_record(_cleaned_id, base_url=base_url)
        except socket.error as se:
            log.error("Socket error...")
            log.error(se)
        except Exception as e:
            log.error("Failed to load {0}. {1} ".format(inspire_id, e))


@shared_task
def import_record(inspire_id, base_url='https://hepdata.net'):
    migrator = Migrator(base_url)

    publication_information, status = migrator.retrieve_publication_information(inspire_id)
    if status != "success":
        log.error("Failed to retrieve publication information for " + inspire_id)
        return False

    current_submission = get_latest_hepsubmission(inspire_id=inspire_id)

    if not current_submission:
        log.info("The record with id {0} does not exist in the database, so we're loading it.".format(inspire_id))
        record_information = create_record(publication_information)
        recid = record_information['recid']
    else:
        log.info("The record with inspire id {0} already exists.".format(inspire_id))
        log.info("Updating instead")
        recid = current_submission.publication_recid

    # Download file to temp dir
    url = "{0}/download/submission/ins{1}/original".format(base_url, inspire_id)
    # Use the next line to allow imports from HEPData.net (for records without
    # additional resources) before PR 289 is merged/released
    # url = "{0}/download/submission/ins{1}/yaml".format(base_url, inspire_id)
    log.info("Trying URL " + url)
    response = requests.get(url)
    if not response.ok:
        log.error('Unable to retrieve download from {0}'.format(url))
        return False
    elif not response.headers['content-type'].startswith('application/'):
        log.error('Did not receive zipped file in response from {0}'.format(url))
        return False

    # save to tmp file
    tmp_file = tempfile.NamedTemporaryFile(mode='wb+', suffix='.zip',
                                           dir=current_app.config["CFG_TMPDIR"],
                                           delete=False)
    tmp_file.write(response.content)
    tmp_file.close()

    time_stamp = str(int(round(time.time())))
    file_save_directory = get_data_path_for_record(str(recid), time_stamp)
    if not os.path.exists(file_save_directory):
        os.makedirs(file_save_directory)
    file_path = os.path.join(file_save_directory,
                             os.path.basename(tmp_file.name))
    shutil.move(tmp_file.name, file_path)

    # Create submission
    admin_user_id = 1
    hepsubmission = get_or_create_hepsubmission(recid, admin_user_id)
    db.session.add(hepsubmission)
    db.session.commit()

    # Then process the payload as for any other record
    errors = process_zip_archive(file_path, recid)
    if errors:
        log.error("Could not process zip archive: ")
        for error in errors:
            log.error("    %s" % error)
        return False

    do_finalise(recid, force_finalise=True,
                update=(current_submission is not None))

