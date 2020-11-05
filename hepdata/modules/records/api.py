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

"""API for HEPData-Records."""
import os
from collections import OrderedDict
from functools import wraps
import subprocess

import time
from celery import shared_task
from flask import redirect, request, render_template, jsonify, current_app, Response, abort, flash
from flask_login import current_user
from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy import and_
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.utils import secure_filename

from hepdata.modules.converter import convert_oldhepdata_to_yaml
from hepdata.modules.email.utils import create_send_email_task
from hepdata.modules.permissions.api import user_allowed_to_perform_action
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.subscribers.api import is_current_user_subscribed_to_record
from hepdata.modules.records.utils.common import decode_string, find_file_in_directory, allowed_file, \
    remove_file_extension, truncate_string, get_record_contents
from hepdata.modules.records.utils.data_processing_utils import process_ctx
from hepdata.modules.records.utils.data_files import get_data_path_for_record, cleanup_old_files
from hepdata.modules.records.utils.submission import process_submission_directory, create_data_review, cleanup_submission
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_action_for_submission_participant
from hepdata.modules.records.utils.yaml_utils import split_files
from hepdata.modules.stats.views import increment, get_count
from hepdata.modules.submission.models import RecordVersionCommitMessage, DataSubmission, HEPSubmission, DataReview
from hepdata.utils.file_extractor import extract
from hepdata.utils.miscellaneous import sanitize_html
from hepdata.utils.users import get_user_from_id
from bs4 import BeautifulSoup
from hepdata_converter_ws_client import Error

import tempfile
import shutil

import logging
logging.basicConfig()
log = logging.getLogger(__name__)

RECORD_PLAIN_TEXT = {
    "passed": "passed review",
    "attention": "attention required",
    "todo": "to be reviewed"
}


def returns_json(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        return Response(r, content_type='application/json; charset=utf-8')

    return decorated_function


def format_submission(recid, record, version, version_count, hepdata_submission,
                      data_table=None):
    """
    Performs all the processing of the record to be displayed.

    :param recid:
    :param record:
    :param version:
    :param version_count:
    :param hepdata_submission:
    :param data_table:
    :return:
    """
    ctx = {}
    if hepdata_submission is not None:

        ctx['site_url'] = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
        ctx['record'] = record
        ctx["version_count"] = version_count

        if version is not -1:
            ctx["version"] = version
        else:
            # we get the latest version by default
            ctx["version"] = version_count

        if record is not None:
            if "collaborations" in record and type(record['collaborations']) is not list:
                collaborations = [x.strip() for x in record["collaborations"].split(",")]
                ctx['record']['collaborations'] = collaborations

            authors = record.get('authors', None)

            create_breadcrumb_text(authors, ctx, record)
            get_commit_message(ctx, recid)

            if authors:
                truncate_author_list(record)

            determine_user_privileges(recid, ctx)

        else:
            ctx['record'] = {}
            determine_user_privileges(recid, ctx)
            ctx['show_upload_widget'] = True
            ctx['show_review_widget'] = False

        ctx['reviewer_count'] = SubmissionParticipant.query.filter_by(
            publication_recid=recid, status="primary", role="reviewer").count()
        ctx['reviewers_notified'] = hepdata_submission.reviewers_notified

        ctx['record']['last_updated'] = hepdata_submission.last_updated
        ctx['record']['hepdata_doi'] = "{0}".format(hepdata_submission.doi)

        if ctx['version'] > 1:
            ctx['record']['hepdata_doi'] += ".v{0}".format(ctx['version'])

        ctx['recid'] = recid
        ctx["status"] = hepdata_submission.overall_status
        ctx['record']['data_abstract'] = sanitize_html(decode_string(hepdata_submission.data_abstract))

        extract_journal_info(record)

        if hepdata_submission.overall_status != 'finished' and ctx["version_count"] > 0:
            if not (ctx['show_review_widget']
                    or ctx['show_upload_widget']
                    or ctx['is_submission_coordinator_or_admin']):
                # we show the latest approved version.
                ctx["version"] -= 1
                ctx["version_count"] -= 1

        ctx['additional_resources'] = submission_has_resources(hepdata_submission)

        # query for a related data submission
        data_record_query = DataSubmission.query.filter_by(
            publication_recid=recid,
            version=ctx["version"]).order_by(DataSubmission.id.asc())

        format_tables(ctx, data_record_query, data_table, recid)

        ctx['access_count'] = get_count(recid)
        ctx['mode'] = 'record'
        ctx['coordinator'] = hepdata_submission.coordinator
        ctx['coordinators'] = get_coordinators_in_system()
        ctx['record'].pop('authors', None)

    return ctx


def format_tables(ctx, data_record_query, data_table, recid):
    """
    Finds all the tables related to a submission and formats
    them for display in the UI or as JSON.

    :return:
    """
    first_data_id = -1
    data_table_metadata, first_data_id = process_data_tables(
        ctx, data_record_query, first_data_id, data_table)
    assign_or_create_review_status(data_table_metadata, recid, ctx["version"])
    ctx['watched'] = is_current_user_subscribed_to_record(recid)
    ctx['table_to_show'] = first_data_id
    if 'table' in request.args:
        if request.args['table']:
            ctx['table_to_show'] = request.args['table']
    ctx['data_tables'] = list(data_table_metadata.values())


def get_commit_message(ctx, recid):
    """
    Returns a commit message for the current version if present.

    :param ctx:
    :param recid:
    """
    try:
        commit_message_query = RecordVersionCommitMessage.query \
            .filter_by(version=ctx["version"], recid=recid)

        if commit_message_query.count() > 0:
            commit_message = commit_message_query.one()
            ctx["revision_message"] = {
                'version': commit_message.version,
                'message': commit_message.message}

    except NoResultFound:
        pass


def create_breadcrumb_text(authors, ctx, record):
    """Creates the breadcrumb text for a submission."""
    if "first_author" in record and 'full_name' in record["first_author"] \
        and record["first_author"]["full_name"] is not None:
        ctx['breadcrumb_text'] = record["first_author"]["full_name"]
        if authors is not None and len(record['authors']) > 1:
            ctx['breadcrumb_text'] += " et al."


def submission_has_resources(hepsubmission):
    """
    Returns whether the submission has resources attached.

    :param hepsubmission: HEPSubmission object
    :return: bool
    """
    return len(hepsubmission.resources) > 0


def extract_journal_info(record):
    if record and 'type' in record:
        if 'thesis' in record['type']:
            if 'type' in record['dissertation']:
                record['journal_info'] = record['dissertation']['type'] + ", " + record['dissertation'][
                    'institution']
            else:
                record['journal_info'] = "PhD Thesis"
        elif 'conference paper' in record['type']:
            record['journal_info'] = "Conference Paper"


def render_record(recid, record, version, output_format, light_mode=False):

    # Count number of all versions and number of finished versions of a publication record.
    version_count_all = HEPSubmission.query.filter(HEPSubmission.publication_recid == recid,
                                                   and_(HEPSubmission.overall_status != 'sandbox',
                                                        HEPSubmission.overall_status != 'sandbox_processing')).count()
    version_count_finished = HEPSubmission.query.filter_by(publication_recid=recid, overall_status='finished').count()

    # Number of versions that a user is allowed to access based on their permissions.
    version_count = version_count_all if user_allowed_to_perform_action(recid) else version_count_finished

    # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
    if version == -1:
        version = version_count if version_count else 1

    # Check for a user trying to access a version of a publication record where they don't have permissions.
    if version_count < version_count_all and version == version_count_all:
        # Prompt the user to login if they are not authenticated then redirect, otherwise return a 403 error.
        if not current_user.is_authenticated:
            redirect_url_after_login = '%2Frecord%2F{0}%3Fversion%3D{1}%26format%3D{2}'.format(recid, version, output_format)
            if 'table' in request.args:
                redirect_url_after_login += '%26table%3D{0}'.format(request.args['table'])
            return redirect('/login/?next={0}'.format(redirect_url_after_login))
        else:
            abort(403)

    hepdata_submission = get_latest_hepsubmission(publication_recid=recid, version=version)

    if hepdata_submission is not None:
        if hepdata_submission.overall_status == 'processing':
            ctx = {'recid': recid}
            determine_user_privileges(recid, ctx)
            return render_template('hepdata_records/publication_processing.html', ctx=ctx)

        elif not hepdata_submission.overall_status.startswith('sandbox'):
            ctx = format_submission(recid, record, version, version_count, hepdata_submission)
            increment(recid)

            if output_format == 'html':
                return render_template('hepdata_records/publication_record.html', ctx=ctx)
            elif 'table' not in request.args:
                if output_format == 'json':
                    ctx = process_ctx(ctx, light_mode)
                    return jsonify(ctx)
                elif output_format == 'yoda' and 'rivet' in request.args:
                    return redirect('/download/submission/{0}/{1}/{2}/{3}'.format(recid, version, output_format,
                                                                              request.args['rivet']))
                else:
                    return redirect('/download/submission/{0}/{1}/{2}'.format(recid, version, output_format))
            else:
                file_identifier = 'ins{}'.format(hepdata_submission.inspire_id) if hepdata_submission.inspire_id else recid
                if output_format == 'yoda' and 'rivet' in request.args:
                    return redirect('/download/table/{0}/{1}/{2}/{3}/{4}'.format(
                        file_identifier, request.args['table'].replace('%', '%25').replace('\\', '%5C'), version, output_format,
                        request.args['rivet']))
                else:
                    return redirect('/download/table/{0}/{1}/{2}/{3}'.format(
                        file_identifier, request.args['table'].replace('%', '%25').replace('\\', '%5C'), version, output_format))
        else:
            abort(404)

    elif record is not None:  # this happens when we access an id of a data record
        # in which case, we find the related publication, and
        # make the front end focus on the relevant data table.
        try:
            publication_recid = int(record['related_publication'])
            publication_record = get_record_contents(publication_recid)

            hepdata_submission = get_latest_hepsubmission(publication_recid=publication_recid)

            ctx = format_submission(publication_recid, publication_record,
                                    hepdata_submission.version, 1, hepdata_submission,
                                    data_table=record['title'])
            ctx['related_publication_id'] = publication_recid
            ctx['table_name'] = record['title']

            if output_format == 'html':
                return render_template('hepdata_records/data_record.html', ctx=ctx)
            elif output_format == 'yoda' and 'rivet' in request.args:
                return redirect('/download/table/{0}/{1}/{2}/{3}/{4}'.format(
                    publication_recid, ctx['table_name'].replace('%', '%25').replace('\\', '%5C'), hepdata_submission.version, output_format,
                    request.args['rivet']))
            else:
                return redirect('/download/table/{0}/{1}/{2}/{3}'.format(
                    publication_recid, ctx['table_name'].replace('%', '%25').replace('\\', '%5C'), hepdata_submission.version, output_format))

        except Exception as e:
            abort(404)
    else:
        abort(404)


def process_payload(recid, file, redirect_url, synchronous=False):
    """Process an uploaded file

    :param recid: int
        The id of the record to update
    :param file: file
        The file to process
    :param redirect_url: string
        Redirect URL to record, for use if the upload fails or in synchronous mode
    :param synchronous: bool
        Whether to process asynchronously via celery (default) or immediately (only recommended for tests)
    :return: JSONResponse either containing 'url' (for success cases) or
             'message' (for error cases, which will give a 400 error).
    """

    if file and (allowed_file(file.filename)):
        file_path = save_zip_file(file, recid)
        hepsubmission = get_latest_hepsubmission(publication_recid=recid)

        if hepsubmission.overall_status == 'finished':
            # If it is finished and we receive an update,
            # then we need to reopen the submission to allow for revisions,
            # by creating a new HEPSubmission object.
            _rev_hepsubmission = HEPSubmission(publication_recid=recid,
                                               overall_status='todo',
                                               inspire_id=hepsubmission.inspire_id,
                                               coordinator=hepsubmission.coordinator,
                                               version=hepsubmission.version + 1)
            db.session.add(_rev_hepsubmission)
            hepsubmission = _rev_hepsubmission

        previous_status = hepsubmission.overall_status
        hepsubmission.overall_status = 'sandbox_processing' if previous_status == 'sandbox' else 'processing'
        db.session.add(hepsubmission)
        db.session.commit()

        if synchronous:
            process_saved_file(file_path, recid, current_user.get_id(), redirect_url, previous_status)
        else:
            process_saved_file.delay(file_path, recid, current_user.get_id(), redirect_url, previous_status)
            flash('File saved. You will receive an email when the file has been processed.', 'info')

        return jsonify({'url': redirect_url.format(recid)})
    else:
        return jsonify({"message": "You must upload a .zip, .tar, .tar.gz or .tgz file" +
                        " (or a .oldhepdata or single .yaml or .yaml.gz file)."}), 400


@shared_task
def process_saved_file(file_path, recid, userid, redirect_url, previous_status):

    hepsubmission = get_latest_hepsubmission(publication_recid=recid)
    if hepsubmission.overall_status != 'processing' and hepsubmission.overall_status != 'sandbox_processing':
        log.error('Record {} is not in a processing state.'.format(recid))
        return

    errors = process_zip_archive(file_path, recid)

    uploader = User.query.get(userid)
    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    submission_participant = SubmissionParticipant.query.filter_by(
        publication_recid=recid, user_account=userid, role='uploader').first()
    if submission_participant:
        full_name = submission_participant.full_name
    else:
        full_name = uploader.email

    if errors:
        cleanup_submission(recid, hepsubmission.version, [])  # delete all tables if errors
        message_body = render_template('hepdata_theme/email/upload_errors.html',
                                       name=full_name,
                                       article=recid,
                                       redirect_url=redirect_url.format(recid),
                                       errors=errors,
                                       site_url=site_url)

        create_send_email_task(uploader.email,
                               '[HEPData] Submission {0} upload failed'.format(recid),
                               message_body)
    else:
        update_action_for_submission_participant(recid, userid, 'uploader')
        message_body = render_template('hepdata_theme/email/upload_complete.html',
                                       name=full_name,
                                       article=recid,
                                       link=redirect_url.format(recid),
                                       site_url=site_url)

        create_send_email_task(uploader.email,
                               '[HEPData] Submission {0} upload succeeded'.format(recid),
                               message_body)

    # Reset the status of the submission back to the previous value.
    hepsubmission.overall_status = previous_status
    db.session.add(hepsubmission)
    db.session.commit()

    # Delete any previous upload folders relating to non-final versions
    # of this hepsubmission
    cleanup_old_files(hepsubmission)


def save_zip_file(file, id):
    filename = secure_filename(file.filename)
    time_stamp = str(int(round(time.time())))
    file_save_directory = get_data_path_for_record(str(id), time_stamp)

    if filename.endswith('.oldhepdata'):
        file_save_directory = os.path.join(file_save_directory, 'oldhepdata')

    if not os.path.exists(file_save_directory):
        os.makedirs(file_save_directory)
    file_path = os.path.join(file_save_directory, filename)

    print('Saving file to {}'.format(file_path))
    file.save(file_path)
    return file_path


def process_zip_archive(file_path, id):
    (file_save_directory, filename) = os.path.split(file_path)

    if not filename.endswith('.oldhepdata'):
        file_save_directory = os.path.dirname(file_path)
        submission_path = os.path.join(file_save_directory, remove_file_extension(filename))
        submission_temp_path = tempfile.mkdtemp(dir=current_app.config["CFG_TMPDIR"])

        if filename.endswith('.yaml.gz'):
            print('Extracting: {} to {}'.format(file_path, file_path[:-3]))
            if not extract(file_path, file_path[:-3]):
                return {
                    "Archive file extractor": [{
                        "level": "error", "message": "{} is not a valid .gz file.".format(file_path)
                    }]
                }
            return process_zip_archive(file_path[:-3], id)
        elif filename.endswith('.yaml'):
            # we split the singular yaml file and create a submission directory
            error, last_updated = split_files(file_path, submission_temp_path)
            if error:
                return {
                    "Single YAML file splitter": [{
                        "level": "error",
                        "message": str(error)
                    }]
                }
        else:
            # we are dealing with a zip, tar, etc. so we extract the contents
            try:
                unzipped_path = extract(file_path, submission_temp_path)
            except Exception as e:
                unzipped_path = None

            if not unzipped_path:
                return {
                    "Archive file extractor": [{
                        "level": "error", "message": "{} is not a valid zip or tar archive file.".format(file_path)
                    }]
                }

        copy_errors = move_files(submission_temp_path, submission_path)
        if copy_errors:
            return copy_errors

        submission_found = find_file_in_directory(submission_path, lambda x: x == "submission.yaml")

        if not submission_found:
            return {
                "Archive file extractor": [{
                    "level": "error", "message": "No submission.yaml file has been found in the archive."
                }]
            }

        basepath, submission_file_path = submission_found
        from_oldhepdata = False

    else:
        file_dir = os.path.dirname(file_save_directory)
        time_stamp = os.path.split(file_dir)[1]
        result = check_and_convert_from_oldhepdata(os.path.dirname(file_save_directory), id, time_stamp)

        # Check for errors
        if type(result) == dict:
            return result
        else:
            basepath, submission_file_path = result
            from_oldhepdata = True

    return process_submission_directory(basepath, submission_file_path, id,
                                        from_oldhepdata=from_oldhepdata)


def check_and_convert_from_oldhepdata(input_directory, id, timestamp):
    """
    Check if the input directory contains a .oldhepdata file
    and convert it to YAML if it happens.
    """
    converted_path = get_data_path_for_record(str(id), timestamp, 'yaml')

    oldhepdata_found = find_file_in_directory(
        input_directory,
        lambda x: x.endswith('.oldhepdata'),
    )
    if not oldhepdata_found:
        return {
            "Converter": [{
                "level": "error",
                "message": "No file with .oldhepdata extension has been found."
            }]
        }

    converted_temp_dir = tempfile.mkdtemp(dir=current_app.config["CFG_TMPDIR"])
    converted_temp_path = os.path.join(converted_temp_dir, 'yaml')

    try:
        successful = convert_oldhepdata_to_yaml(oldhepdata_found[1], converted_temp_path)
        if not successful:
            # Parse error message from title of HTML file, removing part of string after final "//".
            soup = BeautifulSoup(open(converted_temp_path), "lxml")
            errormsg = soup.title.string.rsplit("//", 1)[0]

    except Error as error:  # hepdata_converter_ws_client.Error
        successful = False
        errormsg = str(error)

    if not successful:
        shutil.rmtree(converted_temp_dir, ignore_errors=True)  # can uncomment when this is definitely working

        return {
            "Converter": [{
                "level": "error",
                "message": "The conversion from oldhepdata "
                           "to the YAML format has not succeeded. "
                           "Error message from converter follows:<br/><br/>" + errormsg
            }]
        }
    else:
        copy_errors = move_files(converted_temp_path, converted_path)
        if copy_errors:
            return copy_errors

    return find_file_in_directory(converted_path, lambda x: x == "submission.yaml")


def move_files(submission_temp_path, submission_path):
    print('Copying files from {} to {}'.format(submission_temp_path + '/.', submission_path))
    try:
        shutil.copytree(submission_temp_path, submission_path, symlinks=False)
    except shutil.Error as e:
        errors = []
        for srcname, dstname, exception in e.args[0]:
            # Remove full paths from filenames before sending error message to user
            filename = srcname.replace(submission_temp_path + '/', '')
            msg = str(exception).replace(submission_temp_path + '/', '').replace(submission_path + '/', '')
            errors.append({
                "level": "error",
                "message": 'Invalid file {}: {}'.format(filename, msg)
            })

        return {
            "Exceptions when copying files": errors
        }
    except Exception as e:
        # Remove full paths from filenames before sending error message to user
        msg = str(e).replace(submission_temp_path + '/', '').replace(submission_path + '/', '')
        return {
            "Exceptions when copying files": [{
                "level": "error",
                "message": msg
            }]
        }

    finally:
        shutil.rmtree(submission_temp_path, ignore_errors=True)


def query_messages_for_data_review(data_review_record, messages):
    if data_review_record.messages:
        data_messages = data_review_record.messages
        data_messages.sort(key=lambda data_message: data_message.id, reverse=True)
        for data_message in data_messages:
            current_user_obj = get_user_from_id(data_message.user)
            messages.append(
                {"message": data_message.message,
                 "user": current_user_obj.email,
                 "post_time": data_message.creation_date})

    return messages


def assign_or_create_review_status(data_table_metadata, publication_recid,
                                   version):
    """
    If a review already exists, it will be attached to the current data record.
    If a review does not exist for a data table, it will be created.

    :param data_table_metadata: the metadata describing the main table.
    :param publication_recid: publication record id
    :param version:
    """
    data_review_query = DataReview.query.filter_by(
        publication_recid=publication_recid, version=version)
    # this method should also create all the DataReviews for data_tables that
    # are not currently present to avoid
    # only creating data reviews when the review is clicked explicitly.
    assigned_tables = []
    if data_review_query.count() > 0:
        data_review_records = data_review_query.all()

        for data_review in data_review_records:
            if data_review.data_recid in data_table_metadata:
                data_table_metadata[data_review.data_recid][
                    "review_flag"] = data_review.status
                data_table_metadata[data_review.data_recid]["review_status"] = \
                    RECORD_PLAIN_TEXT[data_review.status]
                data_table_metadata[data_review.data_recid]["messages"] = len(
                    data_review.messages) > 0
                assigned_tables.append(data_review.data_recid)

    # now create the missing data reviews
    for data_table_id in data_table_metadata:
        if data_table_id not in assigned_tables:
            data_record = create_data_review(
                data_table_id, publication_recid, version=version)
            data_table_metadata[data_table_id][
                "review_flag"] = data_record.status
            data_table_metadata[data_table_id]["review_status"] = \
                RECORD_PLAIN_TEXT[data_record.status]


def determine_user_privileges(recid, ctx):
    # show_review_area = not show_upload_area
    ctx['show_review_widget'] = False
    ctx['show_upload_widget'] = False
    ctx['is_submission_coordinator_or_admin'] = False
    ctx['is_admin'] = False

    if current_user.is_authenticated:
        user_id = current_user.get_id()
        participant_records = SubmissionParticipant.query.filter_by(
            user_account=user_id, publication_recid=recid).all()

        for participant_record in participant_records:
            if participant_record is not None:
                if participant_record.role == 'reviewer' and participant_record.status == 'primary':
                    ctx['show_review_widget'] = True

                if participant_record.role == 'uploader' and participant_record.status == 'primary':
                    ctx['show_upload_widget'] = True

        user = User.query.get(current_user.get_id())
        if has_role(user, 'admin'):
            ctx['is_submission_coordinator_or_admin'] = True
            ctx['is_admin'] = True
        else:
            matching_records = HEPSubmission.query.filter_by(
                publication_recid=recid,
                coordinator=current_user.get_id()).count()

            if matching_records > 0:
                ctx['is_submission_coordinator_or_admin'] = True

        ctx['show_upload_widget'] = (
            ctx['show_upload_widget'] or ctx[
                'is_submission_coordinator_or_admin'])


def process_data_tables(ctx, data_record_query, first_data_id,
                        data_table=None):
    data_table_metadata = OrderedDict()
    ctx['show_upload_area'] = False

    if ctx['show_upload_widget'] and data_record_query.count() == 0:
        ctx['show_upload_area'] = True
    elif data_record_query.count() > 0:
        record_submissions = data_record_query.all()
        for submission_record in record_submissions:
            processed_name = "".join(submission_record.name.split())
            data_table_metadata[submission_record.id] = {
                "id": submission_record.id, "processed_name": processed_name,
                "name": submission_record.name,
                "location": submission_record.location_in_publication,
                "doi": submission_record.doi,
                "description": sanitize_html(
                    truncate_string(submission_record.description, 20),
                    tags=[],
                    strip=True
                )
            }

            if first_data_id == -1:
                first_data_id = submission_record.id

            if data_table:
                if submission_record.name == data_table:
                    first_data_id = submission_record.id

    return data_table_metadata, first_data_id


def truncate_author_list(record, length=10):
    record['authors'] = record['authors'][:length]
