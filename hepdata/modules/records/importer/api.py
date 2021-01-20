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

from http.client import responses
import json
import logging
import os
import re
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
from hepdata.modules.records.utils.common import remove_file_extension
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.api import get_latest_hepsubmission

logging.basicConfig()
log = logging.getLogger(__name__)


def import_records(inspire_ids, synchronous=False, update_existing=False,
                   base_url='https://hepdata.net'):
    """
    Import records from hepdata.net
    :param inspire_ids: array of inspire ids to load (in the format insXXX).
    :param synchronous: if should be run immediately rather than via celery
    :param update_existing: whether to update records that already exist
    :param base_url: override default base URL
    :return: None
    """
    for index, inspire_id in enumerate(inspire_ids):
        _cleaned_id = str(inspire_id).replace("ins", "")
        if synchronous:
            import_record(_cleaned_id, update_existing=update_existing,
                          base_url=base_url)
        else:
            log.info("Sending import_record task to celery for id %s"
                     % _cleaned_id)
            import_record.delay(_cleaned_id, update_existing=update_existing,
                                base_url=base_url)


def get_inspire_ids(base_url='https://hepdata.net', last_updated=None, n_latest=None):
    url = base_url + '/search/ids?inspire_ids=true'
    if last_updated:
        url += '&last_updated=' + last_updated.strftime('%Y-%m-%d')

    if n_latest and n_latest > 0:
        url += '&sort_by=latest'

    try:
        response = requests.get(url)
        if not response.ok:
            log.error('Unable to retrieve data from {0}: {1} {2}'.format(
                url, response.status_code, responses.get(response.status_code)
                ))
            log.error('Aborting.')
            return False
    except socket.error as se:
        log.error('Unable to retrieve data from {0}: '.format(url))
        log.error("Socket error: {0}.".format(se))
        log.error("Aborting.")
        return False

    try:
        inspire_ids = response.json()
        if n_latest:
            inspire_ids = inspire_ids[:n_latest]
        return([x for x in inspire_ids])
    except json.decoder.JSONDecodeError:
        log.error('Unexpected response from {0}: {1}'
                  .format(url, response.text))
        return False
    except TypeError:
        log.error('Unexpected response from {0}: {1}'.format(url, inspire_ids))
        return False


@shared_task
def import_record(inspire_id, update_existing=False, base_url='https://hepdata.net'):
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
        if update_existing:
            log.info("Updating instead")
            recid = current_submission.publication_recid
        else:
            log.info("Not updating as update_existing is False")
            return False

    # Download file to temp dir
    url = "{0}/download/submission/ins{1}/original".format(base_url, inspire_id)
    # Use the next line to allow imports from HEPData.net (for records without
    # additional resources) before PR 289 is merged/released
    url = "{0}/download/submission/ins{1}/yaml".format(base_url, inspire_id)
    log.info("Trying URL " + url)
    try:
        response = requests.get(url)
        if not response.ok:
            log.error('Unable to retrieve download from {0}'.format(url))
            return False
        elif not response.headers['content-type'].startswith('application/'):
            log.error('Did not receive zipped file in response from {0}'.format(url))
            return False
    except socket.error as se:
        log.error("Socket error: %s" % se)
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

    # Try getting file name from headers (but fall back to tmp file name)
    filename = os.path.basename(tmp_file.name)
    if 'content-disposition' in response.headers:
        match = re.search("filename=(.+)", response.headers['content-disposition'])
        if match:
            filename = match.group(1)

    file_path = os.path.join(file_save_directory,
                             filename)
    log.info("Moving file to %s" % file_path)
    shutil.move(tmp_file.name, file_path)

    # Create submission
    admin_user_id = 1
    hepsubmission = get_or_create_hepsubmission(recid, admin_user_id)
    db.session.add(hepsubmission)
    db.session.commit()

    # Then process the payload as for any other record
    errors = process_zip_archive(file_path, recid)
    if errors:
        log.info("Errors processing archive. Re-trying with old schema.")
        # Try again with old schema
        # Need to clean up first to avoid errors
        file_save_directory = os.path.dirname(file_path)
        submission_path = os.path.join(file_save_directory, remove_file_extension(filename))
        shutil.rmtree(submission_path)

        errors = process_zip_archive(file_path, recid, old_submission_schema=True)

        if errors:
            log.error("Could not process zip archive: ")
            for file, file_errors in errors.items():
                log.error("    %s:" % file)
                for error in file_errors:
                    log.error("        %s" % error['message'])

            return False

    log.info("Finalising record %s" % recid)

    do_finalise(recid, force_finalise=True,
                update=(current_submission is not None))

    log.info("Imported record %s." % recid)
