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
import hashlib
import logging
import os
import shutil

from celery import shared_task
from flask import current_app
from invenio_db import db

from hepdata.modules.email.utils import create_send_email_task
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission, HEPSubmission, DataResource

logging.basicConfig()
log = logging.getLogger(__name__)


def find_submission_data_file_path(submission):
    """Find the data file path for a submission. Looks in both old
    and new directory patterns."""
    # Try old location as well as new, so downloads still work whilst files
    # are being migrated
    data_filename = current_app.config['SUBMISSION_FILE_NAME_PATTERN'] \
                               .format(submission.publication_recid,
                                       submission.version)

    path = get_data_path_for_record(str(submission.publication_recid),
                                    data_filename)

    if not os.path.isfile(path):
        path = get_old_data_path_for_record(str(submission.publication_recid),
                                            data_filename)
    return path


def get_converted_directory_path(record_id):
    """Return the path for converted files for the given record id"""
    return os.path.join(current_app.config['CFG_DATADIR'],
                        'converted',
                        get_subdir_name(record_id))


def get_data_path_for_record(record_id, *subpaths):
    """Return the path for data files for the given record id."""
    path = os.path.join(current_app.config['CFG_DATADIR'],
                        get_subdir_name(record_id),
                        record_id,
                        *subpaths)
    return path


def get_old_data_path_for_record(record_id, *subpaths):
    """Return the path for data files for the given record id."""
    path = os.path.join(current_app.config['CFG_DATADIR'],
                        record_id,
                        *subpaths)
    return path


def get_subdir_name(record_id):
    hash_object = hashlib.sha256(record_id.encode())
    hex_dig = hash_object.hexdigest()
    return str(hex_dig)[:2]


def move_data_files(record_ids, synchronous=False):
    if record_ids is None:
        qry = db.session.query(HEPSubmission.publication_recid)
        result = qry.all()
        record_ids = [r[0] for r in result]

    log.info("Got records: %s" % record_ids)
    if not synchronous:
        log.info("Sending tasks to celery.")

    for rec_id in record_ids:
        if synchronous:
            move_files_for_record(rec_id)
        else:
            move_files_for_record.delay(rec_id)


@shared_task
def move_files_for_record(rec_id):
    log.debug("Moving files for record %s" % rec_id)
    hep_submission = get_latest_hepsubmission(publication_recid=rec_id)
    errors = []

    # Need to check both rec_id (for newer submissions) and inspire_id
    # (for migrated submissions)
    old_paths = [get_old_data_path_for_record(str(rec_id))]
    if hep_submission.inspire_id is not None:
        old_paths.append(get_old_data_path_for_record('ins%s' % hep_submission.inspire_id))

    old_paths = [path for path in old_paths if os.path.isdir(path)]

    new_path = get_data_path_for_record(str(rec_id))
    log.debug("Moving files from %s to %s" % (old_paths, new_path))

    os.makedirs(new_path, exist_ok=True)

    # Move data submissions
    data_submissions = DataSubmission.query.filter_by(
                            publication_recid=rec_id
                            ).all()
    for data_submission in data_submissions:
        # Get file_location
        resource = DataResource.query.filter_by(
                        id=data_submission.data_file
                        ).first()

        log.debug("    Checking file %s" % resource.file_location)

        if resource.file_location.startswith(new_path):
            log.debug("    File already in new location. Continuing.")
            continue

        sub_path = None
        for path in old_paths:
            if resource.file_location.startswith(path):
                sub_path = resource.file_location.split(path + '/', 1)[1]
                break

        if sub_path:
            new_file_path = os.path.join(new_path, sub_path)
            log.debug("    Moving to new path %s" % new_file_path)
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            try:
                shutil.move(resource.file_location, new_file_path)
            except Exception as e:
                errors.append("Unable to move file from %s to %s for data resource id %s\n"
                              "Error was: %s"
                              % (resource.file_location, new_file_path, resource.id, str(e)))

            log.debug("    Updating data record")
            resource.file_location = new_file_path
            db.session.add(resource)
            db.session.commit()

        else:
            log.debug("    Location %s not recognised" % resource.file_location)
            errors.append("Location %s not recognised for data resource id %s"
                          % (resource.file_location, resource.id))

    # Move rest of files in old_paths
    for old_path in old_paths:
        for f in os.listdir(old_path):
            log.debug("Moving file %s" % f)
            try:
                shutil.move(os.path.join(old_path, f), os.path.join(new_path, f))
            except Exception as e:
                errors.append("Unable to move file from %s to %s\n"
                              "Error was: %s"
                              % (os.path.join(old_path, f), os.path.join(new_path, f),
                                 resource.id, str(e)))

        # Remove directory, which should be empty
        try:
            os.rmdir(old_path)
        except Exception as e:
            errors.append("Unable to remove directory %s\n"
                          "Error was: %s"
                          % (old_path, str(e)))

    # TODO: send an email with details of errors
    if errors:
        message = "<div>ERRORS moving files for record id %s:<ul><li>\n%s</li></ul></div>" \
                  % (rec_id, '</li><li>'.join(errors).replace('\n', '<br>'))

        create_send_email_task(current_app.config['ADMIN_EMAIL'],
                               subject="[HEPData] Errors moving files for record id %s" % rec_id,
                               message=message,
                               reply_to_address=current_app.config['ADMIN_EMAIL'])


def delete_old_converted_files():
    with os.scandir(os.path.join(current_app.config['CFG_DATADIR'],
                    'converted')) as entries:
        for entry in entries:
            if entry.is_file() or entry.is_symlink():
                os.remove(entry.path)
            elif entry.is_dir():
                shutil.rmtree(entry.path)
