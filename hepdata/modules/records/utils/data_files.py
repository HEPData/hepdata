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
from hepdata.modules.records.utils.common import allowed_file
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission, HEPSubmission, DataResource
from hepdata.utils.celery import count_tasks_in_queue

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
                        _get_subdir_name(record_id))


def get_data_path_for_record(record_id, *subpaths):
    """Return the path for data files for the given record id."""
    path = os.path.join(current_app.config['CFG_DATADIR'],
                        _get_subdir_name(record_id),
                        str(record_id),
                        *subpaths)
    return path


def get_old_data_path_for_record(record_id, *subpaths):
    """Return the path for data files for the given record id."""
    path = os.path.join(current_app.config['CFG_DATADIR'],
                        str(record_id),
                        *subpaths)
    return path


def _get_subdir_name(record_id):
    hash_object = hashlib.sha256(str(record_id).encode())
    hex_dig = hash_object.hexdigest()
    return str(hex_dig)[:2]


def delete_packaged_file(hepsubmission):
    """
    Deletes the packaged data file for the given submission
    """
    packaged_filepath = find_submission_data_file_path(hepsubmission)
    if os.path.isfile(packaged_filepath):
        log.debug("Removing %s" % packaged_filepath)
        os.remove(packaged_filepath)


def delete_all_files(rec_id, check_old_data_paths=True):
    """
    Deletes all data files across ALL versions of a record.
    """
    record_data_paths = [get_data_path_for_record(rec_id)]

    if check_old_data_paths:
        record_data_paths.append(get_old_data_path_for_record(rec_id))
        hepsubmission = get_latest_hepsubmission(publication_recid=rec_id)
        if hepsubmission and hepsubmission.inspire_id is not None:
            record_data_paths.append(get_old_data_path_for_record('ins%s' % hepsubmission.inspire_id))

    for record_data_path in record_data_paths:
        log.debug("Scanning directory: %s" % record_data_path)

        if os.path.isdir(record_data_path):
            log.debug("Removing %s" % record_data_path)
            shutil.rmtree(record_data_path)


def cleanup_old_files(hepsubmission, check_old_data_paths=True):
    """Remove old files not related to a current version of the submission"""
    rec_id = str(hepsubmission.publication_recid)
    record_data_paths = [get_data_path_for_record(rec_id)]

    if check_old_data_paths:
        record_data_paths.append(get_old_data_path_for_record(rec_id))
        if hepsubmission.inspire_id is not None:
            record_data_paths.append(get_old_data_path_for_record('ins%s' % hepsubmission.inspire_id))

    current_filepaths = set()

    path_prefixes = [f"{path}/" for path in record_data_paths]
    current_resources = _find_all_current_dataresources(hepsubmission.publication_recid)

    for r in current_resources:
        if not r.file_location.startswith('http'):
            found = False
            for path_prefix in path_prefixes:
                if r.file_location.startswith(path_prefix):
                    subdirs = r.file_location.split(path_prefix, 1)[1]
                    top_subdir = subdirs.split(os.sep, 1)[0]
                    current_filepaths.add(os.path.join(path_prefix, top_subdir))
                    found = True
                    break

            if not found:
                log.warning("Unknown file %s" % r.file_location)

    packaged_filepath = find_submission_data_file_path(hepsubmission)
    packaged_filename = os.path.basename(packaged_filepath)

    for record_data_path in record_data_paths:
        log.debug("Scanning directory: %s" % record_data_path)

        if os.path.isdir(record_data_path):
            with os.scandir(record_data_path) as entries:
                for entry in entries:
                    if entry.is_dir() and \
                            entry.path not in current_filepaths:
                        log.debug("Removing %s" % entry.path)
                        shutil.rmtree(entry.path)

                    elif entry.name == packaged_filename and \
                            entry.path != packaged_filepath:
                        # Corner case: new upload uses new data
                        # file path, but previous upload still uses old path
                        # Need to delete packaged file in old path.
                        log.debug("Removing %s" % entry.path)
                        os.remove(entry.path)


def _find_all_current_dataresources(rec_id):
    """Get all DataResource objects associated with all versions of the record"""
    hep_submissions = HEPSubmission.query.filter_by(
                        publication_recid=rec_id
                        ).all()
    resources = []
    for submission in hep_submissions:
        resources.extend(submission.resources)

    data_submissions = DataSubmission.query.filter_by(
                            publication_recid=rec_id
                            ).all()
    for data_submission in data_submissions:
        resources.append(DataResource.query.filter_by(
                            id=data_submission.data_file
                            ).first())
        resources.extend(data_submission.resources)

    return resources


def move_inspire_data_files(inspire_output_location, recid):
    """Moves output location based on inspire_id to new location based on
    record id. For use by migrator where files are retrieved before a record
    is created.
    """
    print("Moving inspire data files")
    output_location = get_data_path_for_record(recid)
    paths_to_delete = []

    if os.path.isdir(output_location):
        # move individual entries to new location
        with os.scandir(inspire_output_location) as entries:
            for entry in entries:
                shutil.move(entry.path, os.path.join(output_location, entry.name))
        # Delete parent dir
        paths_to_delete.append(inspire_output_location)
    else:
        # Can just move whole directory
        shutil.move(inspire_output_location, output_location)

    paths_to_delete.append(os.path.dirname(inspire_output_location))

    for path in paths_to_delete:
        try:
            os.rmdir(path)
        except OSError:
            pass

    print("Returning %s" %output_location)
    return output_location


# Functions below relate to cli clean up and move data files functions
# (see https://github.com/HEPData/hepdata/issues/139 and
# https://github.com/HEPData/hepdata/issues/218) - we may be able to
# remove them once the cleanup has been run.

def cleanup_all_resources(synchronous=False):  # pragma: no cover
    """Cleans up unused resources for all records
    First checks for orphaned data resources in the db and deletes them.
    Then goes through all records and deletes unused files on disk.
    """
    if _check_for_running_tasks():
        # exit as tasks are currently running
        return

    # Clean up all orphaned file resources
    _delete_all_orphan_file_resources()

    # Iterate through all records and clean up old files
    qry = db.session.query(HEPSubmission.publication_recid)
    result = qry.distinct()
    record_ids = [r[0] for r in result]

    log.info("Got records: %s" % record_ids)

    if not synchronous:
        log.info("Sending tasks to celery.")

    for rec_id in record_ids:
        if synchronous:
            _cleanup_old_files_for_record(rec_id)
        else:
            _cleanup_old_files_for_record.delay(rec_id)


def _check_for_running_tasks():
    # Check celery queue to ensure any data files tasks have finished
    # (or are not running)
    data_files_task_count = count_tasks_in_queue(task_name_prefix=_check_for_running_tasks.__module__)

    if data_files_task_count > 0:
        log.error("%s data files tasks are still running. Try again later."
                  % data_files_task_count)
        return True
    else:
        return False


def _delete_all_orphan_file_resources():  # pragma: no cover
    """Deletes all entries in the DataResource table which do not map to
    an existing HEPSubmission or DataSubmission.
    """
    # We need to lock the tables from which we are selecting until
    # we have a full set of valid resource ids, to ensure we don't delete
    # new entries.
    # Current stats:
    # ~8k rows in data_resource_link - explain analyse on QA takes 10ms
    # ~258k data submissions - explain analyse on QA takes 239ms
    # ~196k rows in datafile_identifier - explain analyse on QA takes 92ms
    # Produces ~300k orphans on QA.
    result = db.session.execute(
        """
        CREATE TEMP TABLE valid_resource_ids(id INT);
        LOCK TABLE data_resource_link IN EXCLUSIVE MODE;
        INSERT INTO valid_resource_ids
            SELECT dataresource_id FROM data_resource_link;
        LOCK TABLE datasubmission IN EXCLUSIVE MODE;
        INSERT INTO valid_resource_ids
            SELECT data_file FROM datasubmission;
        LOCK TABLE datafile_identifier IN EXCLUSIVE MODE;
        INSERT INTO valid_resource_ids
            SELECT dataresource_id FROM datafile_identifier;
        SELECT id FROM dataresource
            WHERE NOT EXISTS (
                 SELECT id from valid_resource_ids
                    WHERE valid_resource_ids.id = dataresource.id
            );
        """
    )

    ids_to_delete = [x[0] for x in result]
    db.session.rollback()

    # Batch up the ids to delete, and use the SQLAlchemy objects
    # to do the deletion, to ensure the files are also deleted from disk.
    count = 0
    batch_size = 100
    while count <= len(ids_to_delete):
        end = min(len(ids_to_delete), count+batch_size)
        batch = list(ids_to_delete[count:end])
        _delete_orphan_dataresource_batch.delay(batch)
        count += batch_size


@shared_task
def _delete_orphan_dataresource_batch(ids):  # pragma: no cover
    """Deletes the data resources with the given ids."""
    resources = DataResource.query.filter(DataResource.id.in_(ids)).all()
    for resource in resources:
        db.session.delete(resource)

    db.session.commit()


@shared_task
def _cleanup_old_files_for_record(rec_id):  # pragma: no cover
    """Wrapper method for use by celery when cleaning old files"""
    hepsubmission = get_latest_hepsubmission(publication_recid=rec_id)
    cleanup_old_files(hepsubmission, check_old_data_paths=True)


def move_data_files(record_ids, synchronous=False):  # pragma: no cover
    """Move data files to new location, i.e. using a hash for a
    subdirectory to reduce the number of directories on the disk.
    """
    if _check_for_running_tasks():
        # exit as tasks are currently running
        return

    if record_ids is None:
        qry = db.session.query(HEPSubmission.publication_recid)
        result = qry.distinct()
        record_ids = [r[0] for r in result]

    log.info("Got records: %s" % record_ids)

    if not synchronous:
        log.info("Sending tasks to celery.")

    for rec_id in record_ids:
        if synchronous:
            _move_files_for_record(rec_id)
        else:
            _move_files_for_record.delay(rec_id)


@shared_task
def _move_files_for_record(rec_id):  # pragma: no cover
    """Move data files for given record from old to new location."""
    log.debug("Moving files for record %s" % rec_id)
    hep_submissions = HEPSubmission.query.filter_by(
                        publication_recid=rec_id
                        ).all()
    errors = []

    # Need to check both rec_id (for newer submissions) and inspire_id
    # (for migrated submissions)
    old_paths = [get_old_data_path_for_record(rec_id)]
    inspire_id = hep_submissions[0].inspire_id
    if inspire_id is not None:
        old_paths.append(get_old_data_path_for_record('ins%s' % inspire_id))
        old_paths.append(get_old_data_path_for_record(inspire_id))

    log.debug("Checking old paths %s" % old_paths)

    old_paths = [path for path in old_paths if os.path.isdir(path)]

    new_path = get_data_path_for_record(rec_id)
    log.debug("Moving files from %s to %s" % (old_paths, new_path))

    os.makedirs(new_path, exist_ok=True)

    # Find all data resources
    resources = _find_all_current_dataresources(rec_id)
    for resource in resources:
        resource_errors = _move_data_resource(resource, old_paths, new_path)
        errors.extend(resource_errors)

    # Move rest of files in old_paths
    for old_path in old_paths:
        for dir_name, subdir_list, file_list in os.walk(old_path):
            for filename in file_list:
                if allowed_file(filename):
                    full_path = os.path.join(dir_name, filename)
                    log.debug("Found remaining file: %s" % full_path)
                    sub_path = full_path.split(old_path + '/', 1)[1]
                    new_file_path = os.path.join(new_path, sub_path)
                    log.debug("Moving %s to %s" % (full_path, new_file_path))
                    try:
                        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
                        shutil.move(full_path, new_file_path)
                    except Exception as e:
                        errors.append("Unable to move file from %s to %s\n"
                                      "Error was: %s"
                                      % (full_path, new_file_path, str(e)))
                else:
                    errors.append("Unrecognized file %s. Will not move file."
                                  % filename)

        # Remove directories, which should be empty
        for dirpath, _, _ in os.walk(old_path, topdown=False):
            log.debug("Removing directory %s" % dirpath)
            try:
                os.rmdir(dirpath)
            except Exception as e:
                errors.append("Unable to remove directory %s\n"
                              "Error was: %s"
                              % (dirpath, str(e)))

    # If there's a zip file from the migration, move that to the new dir too.
    if inspire_id is not None:
        zip_name = f'ins{inspire_id}.zip'
        old_zip_path = os.path.join(current_app.config['CFG_DATADIR'],
                                    zip_name)
        if os.path.isfile(old_zip_path):
            try:
                new_zip_path = os.path.join(new_path, zip_name)
                shutil.move(old_zip_path, new_zip_path)
            except Exception as e:
                errors.append("Unable to move archive file from %s to %s\n"
                              "Error was: %s"
                              % (old_zip_path, new_zip_path, str(e)))

    # Send an email with details of errors
    if errors:
        log.error(errors)
        message = "<div>ERRORS moving files for record id %s:<ul><li>\n%s</li></ul></div>" \
                  % (rec_id, '</li><li>'.join(errors).replace('\n', '<br>'))

        create_send_email_task(current_app.config['ADMIN_EMAIL'],
                               subject="[HEPData] Errors moving files for record id %s" % rec_id,
                               message=message,
                               reply_to_address=current_app.config['ADMIN_EMAIL'])


def _move_data_resource(resource, old_paths, new_path):  # pragma: no cover
    errors = []
    log.debug("    Checking file %s" % resource.file_location)

    if resource.file_location.startswith(new_path):
        log.debug("    File already in new location. Continuing.")
        return errors

    if resource.file_location.startswith('http'):
        log.debug("    File is remote URL. Continuing.")
        return errors

    sub_path = None
    for path in old_paths:
        if resource.file_location.startswith(path):
            sub_path = resource.file_location.split(path + '/', 1)[1]
            break

    if sub_path:
        new_file_path = os.path.join(new_path, sub_path)
        log.debug("    Moving to new path %s" % new_file_path)
        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
        if os.path.exists(resource.file_location):
            try:
                shutil.move(resource.file_location, new_file_path)
            except Exception as e:
                errors.append("Unable to move file from %s to %s for data resource id %s\n"
                              "Error was: %s"
                              % (resource.file_location, new_file_path, resource.id, str(e)))

        elif not os.path.exists(new_file_path):
            # File does not exist in old or new locations - something has gone wrong
            errors.append("File for for data resource id %s does not exist at "
                          "either old path (%s) or new path (%s)"
                          % (resource.id, resource.file_location, new_file_path))

        log.debug("    Updating data record")
        resource.file_location = new_file_path
        db.session.add(resource)
        db.session.commit()

    else:
        log.debug("    Location %s not recognised" % resource.file_location)
        errors.append("Location %s not recognised for data resource id %s"
                      % (resource.file_location, resource.id))

    return errors


def delete_old_converted_files():  # pragma: no cover
    converted_path = os.path.join(current_app.config['CFG_DATADIR'],
                                  'converted')
    if os.path.isdir(converted_path):
        with os.scandir(converted_path) as entries:
            for entry in entries:
                if entry.is_file() or entry.is_symlink():
                    os.remove(entry.path)
                elif entry.is_dir():
                    shutil.rmtree(entry.path)


def clean_remaining_files(synchronous=True):  # pragma: no cover
    """
    Looks for files in data dir that do not match a known pattern.
    For folders that look like a sandbox record (timestamp), check db
    and delete.
    For everything else, display on the console and send an email.
    """
    if _check_for_running_tasks():
        # exit as tasks are currently running
        return

    unknown_files = []

    data_dir = current_app.config['CFG_DATADIR']
    with os.scandir(data_dir) as entries:
        for entry in entries:
            log.debug("Checking %s" % entry.path)
            recognised = False
            if entry.is_dir():
                # If dirname has 2 chars it's in our expected format.
                if entry.name == 'converted':
                    recognised = True
                elif len(entry.name) == 2:
                    # Valid dir, but also check subpaths
                    recognised = True
                    with os.scandir(entry.path) as subdir_entries:
                        for sub_entry in subdir_entries:
                            if not sub_entry.name.isdigit():
                                unknown_files.append(sub_entry.path)
                else:
                    # Is it a deleted sandbox entry?
                    if len(entry.name) == 10 and \
                            entry.name.isdigit():
                        # This is probably a deleted sandbox entry
                        recognised = True
                        rec_id = int(entry.name)
                        submission_count = HEPSubmission.query.filter_by(publication_recid=rec_id).count()
                        if submission_count == 0:
                            log.debug("Deleting %s" %entry.path)
                            shutil.rmtree(entry.path)
                        else:
                            log.warning("Sandbox entry %s is still in old file location" % entry.name)

            if not recognised:
                unknown_files.append(entry.path)

    if unknown_files:
        print("The following files/directories were found in %s which were not recognised:" % data_dir)
        for f in unknown_files:
            print("    %s" % f)

        print("These files will remain on the filesystem unless they are manually cleaned up.")

        print("Sending email with this info.")
        message = "<div>After moving files, the following files/directories were found in %s which were not recognised:"\
                  "<ul><li>\n%s</li></ul>" \
                  "<p>These files will remain on the filesystem unless they are manually cleaned up.</p></div>" \
                  % (data_dir, '</li><li>'.join(unknown_files))

        create_send_email_task(current_app.config['ADMIN_EMAIL'],
                               subject="[HEPData] Files remaining in %s after migration" % data_dir,
                               message=message,
                               reply_to_address=current_app.config['ADMIN_EMAIL'])
