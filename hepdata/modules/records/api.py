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
from flask import redirect, request, render_template, jsonify, current_app, Response, abort
from flask_login import current_user
from invenio_accounts.models import User
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.utils import secure_filename

from hepdata.modules.converter import convert_oldhepdata_to_yaml
from hepdata.modules.permissions.api import user_allowed_to_perform_action
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.subscribers.api import is_current_user_subscribed_to_record
from hepdata.modules.records.utils.common import decode_string, find_file_in_directory, allowed_file, \
    remove_file_extension, truncate_string, get_record_contents
from hepdata.modules.records.utils.data_processing_utils import process_ctx
from hepdata.modules.records.utils.submission import process_submission_directory, create_data_review
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_action_for_submission_participant
from hepdata.modules.records.utils.yaml_utils import split_files
from hepdata.modules.stats.views import increment, get_count
from hepdata.modules.submission.models import RecordVersionCommitMessage, DataSubmission, HEPSubmission, DataReview
from hepdata.utils.file_extractor import extract
from hepdata.utils.users import get_user_from_id
from bs4 import BeautifulSoup

import tempfile
from shutil import rmtree

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
        ctx['record']['data_abstract'] = decode_string(hepdata_submission.data_abstract)

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
    ctx['data_tables'] = data_table_metadata.values()


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
        elif 'conferencepaper' in record['type']:
            record['journal_info'] = "Conference Paper"


def render_record(recid, record, version, output_format, light_mode=False):

    # Count number of all versions and number of finished versions of a publication record.
    version_count_all = HEPSubmission.query.filter(HEPSubmission.publication_recid == recid,
                                                   HEPSubmission.overall_status != 'sandbox').count()
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
        if hepdata_submission.overall_status != 'sandbox':
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


def process_payload(recid, file, redirect_url):
    if file and (allowed_file(file.filename)):
        errors = process_zip_archive(file, recid)
        if errors:
            return render_template('hepdata_records/error_page.html',
                                   redirect_url=redirect_url.format(recid), errors=errors)
        else:
            update_action_for_submission_participant(recid, current_user.get_id(), 'uploader')
            return redirect(redirect_url.format(recid))
    else:
        return render_template('hepdata_records/error_page.html', redirect_url=redirect_url.format(recid),
                               message="Incorrect file type uploaded.",
                               errors={"Submission": [{"level": "error",
                                                       "message": "You must upload a .zip, .tar, .tar.gz or .tgz file"
                                                                  + " (or a .oldhepdata or single .yaml file)."}]})


def process_zip_archive(file, id):
    filename = secure_filename(file.filename)
    time_stamp = str(int(round(time.time())))
    file_save_directory = os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp)

    if not os.path.exists(file_save_directory):
        os.makedirs(file_save_directory)

    if not filename.endswith('.oldhepdata'):
        file_path = os.path.join(file_save_directory, filename)
        print('Saving file to {}'.format(file_path))
        file.save(file_path)

        submission_path = os.path.join(file_save_directory, remove_file_extension(filename))
        submission_temp_path = tempfile.mkdtemp(dir=current_app.config["CFG_TMPDIR"])

        if filename.endswith('.yaml'):
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
            if not extract(file_path, submission_temp_path):
                return {
                    "Archive file extractor": [{
                        "level": "error", "message": "{} is not a valid zip or tar archive file.".format(file_path)
                    }]
                }

        if not os.path.exists(submission_path):
            os.makedirs(submission_path)

        copy_command = ['cp']
        print('Copying with: {} -r {} {}'.format(' '.join(copy_command), submission_temp_path + '/.', submission_path))
        subprocess.check_output(copy_command + ['-r',  submission_temp_path + '/.', submission_path])
        rmtree(submission_temp_path, ignore_errors=True) # can uncomment when this is definitely working

        submission_found = find_file_in_directory(submission_path, lambda x: x == "submission.yaml")

    else:
        file_path = os.path.join(file_save_directory, 'oldhepdata')
        if not os.path.exists(file_path):
            os.makedirs(file_path)

        print('Saving file to {}'.format(os.path.join(file_path, filename)))
        file.save(os.path.join(file_path, filename))

        submission_found = False

    if submission_found:
        basepath, submission_file_path = submission_found
        from_oldhepdata = False
    else:
        result = check_and_convert_from_oldhepdata(file_path, id, time_stamp)

        # Check for errors
        if type(result) == dict:
            return result
        else:
            basepath, submission_file_path = result
            from_oldhepdata = True

    return process_submission_directory(basepath, submission_file_path, id, from_oldhepdata=from_oldhepdata)


def check_and_convert_from_oldhepdata(input_directory, id, timestamp):
    """
    Check if the input directory contains a .oldhepdata file
    and convert it to YAML if it happens.
    """
    converted_path = os.path.join(current_app.config['CFG_DATADIR'], str(id), timestamp, 'yaml')

    if not os.path.exists(converted_path):
        os.makedirs(converted_path)

    oldhepdata_found = find_file_in_directory(
        input_directory,
        lambda x: x.endswith('.oldhepdata'),
    )
    if not oldhepdata_found:
        return {
            "Converter": [{
                "level": "error",
                "message": "No file with .oldhepdata extension or a submission.yaml"
                           " file has been found in the archive."
            }]
        }

    converted_temp_dir = tempfile.mkdtemp(dir=current_app.config["CFG_TMPDIR"])
    converted_temp_path = os.path.join(converted_temp_dir, 'yaml')

    successful = convert_oldhepdata_to_yaml(oldhepdata_found[1], converted_temp_path)
    if not successful:
        # Parse error message from title of HTML file, removing part of string after final "//".
        soup = BeautifulSoup(open(converted_temp_path), "lxml")
        errormsg = soup.title.string.rsplit("//", 1)[0]
        rmtree(converted_temp_dir, ignore_errors=True) # can uncomment when this is definitely working

        return {
            "Converter": [{
                "level": "error",
                "message": "The conversion from oldhepdata "
                           "to the YAML format has not succeeded. "
                           "Error message from converter follows.\n" + errormsg
            }]
        }
    else:
        copy_command = ['cp']
        print('Copying with: {} -r {} {}'.format(' '.join(copy_command), converted_temp_path + '/.', converted_path))
        subprocess.check_output(copy_command + ['-r', converted_temp_path + '/.', converted_path])
        rmtree(converted_temp_dir, ignore_errors=True) # can uncomment when this is definitely working

    return find_file_in_directory(converted_path, lambda x: x == "submission.yaml")


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
                "description": decode_string(
                    truncate_string(submission_record.description, 20))}

            if first_data_id == -1:
                first_data_id = submission_record.id

            if data_table:
                if submission_record.name == data_table:
                    first_data_id = submission_record.id

    return data_table_metadata, first_data_id


def truncate_author_list(record, length=10):
    record['authors'] = record['authors'][:length]
