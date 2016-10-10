# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

import time
from flask import redirect, request, render_template, jsonify, current_app, Response
from flask.ext.login import current_user
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
from hepdata.modules.records.utils.submission import process_submission_directory, \
    remove_submission, create_data_review
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_action_for_submission_participant
from hepdata.modules.records.utils.yaml_utils import split_files
from hepdata.modules.stats.views import increment, get_count
from hepdata.modules.submission.models import RecordVersionCommitMessage, DataSubmission, HEPSubmission, DataReview
from hepdata.utils.file_extractor import extract
from hepdata.utils.users import get_user_from_id

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
    Performs all the processing of the record to be display
    :param recid:
    :param record:
    :param version:
    :param hepdata_submission:
    :param data_table:
    :return:
    """
    ctx = {}
    if hepdata_submission is not None:

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
    Finds all the tables related to a submission and generates formats
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
        if request.args['table'] is not '':
            ctx['table_to_show'] = request.args['table']
    ctx['data_tables'] = data_table_metadata.values()


def get_commit_message(ctx, recid):
    """
    Returns a commit message for the current version if present
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
    """
    Creates the breadcrumb text for a submission
    """
    if "first_author" in record and 'full_name' in record["first_author"]\
        and record["first_author"]["full_name"] is not None:
        ctx['breadcrumb_text'] = record["first_author"]["full_name"]
        if authors is not None and len(record['authors']) > 1:
            ctx['breadcrumb_text'] += " et al."


def submission_has_resources(hepsubmission):
    """
    Returns if the submission has resources attached
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

    if user_allowed_to_perform_action(recid):
        version_count = HEPSubmission.query.filter_by(
            publication_recid=recid).count()
    else:
        version_count = HEPSubmission.query.filter_by(
            publication_recid=recid, overall_status='finished').count()

    if version == -1:
        version = version_count

    hepdata_submission = get_latest_hepsubmission(publication_recid=recid, version=version)

    if hepdata_submission is not None:
        ctx = format_submission(recid, record, version, version_count, hepdata_submission)
        increment(recid)
        if output_format == "json":
            ctx = process_ctx(ctx, light_mode)
            return jsonify(ctx)
        else:
            return render_template('hepdata_records/publication_record.html',
                                   ctx=ctx)

    else:  # this happens when we access an id of a data record
        # in which case, we find the related publication, and
        # make the front end focus on the relevant data table.
        try:
            publication_recid = int(record['related_publication'])
            publication_record = get_record_contents(publication_recid)

            hepdata_submission = get_latest_hepsubmission(recid=publication_recid)

            ctx = format_submission(publication_recid, publication_record,
                                    hepdata_submission.version, 1, hepdata_submission,
                                    data_table=record['title'])
            ctx['related_publication_id'] = publication_recid
            ctx['table_name'] = record['title']

            if output_format == "json":
                ctx = process_ctx(ctx, light_mode)

                return jsonify(ctx)
            else:
                return render_template('hepdata_records/data_record.html', ctx=ctx)
        except Exception:
            return render_template('hepdata_theme/404.html')


def process_payload(recid, file, redirect_url):
    if file and (allowed_file(file.filename)):
        errors = process_zip_archive(file, recid)
        if errors:
            remove_submission(recid)
            return render_template('hepdata_records/error_page.html',
                                   recid=None, errors=errors)
        else:
            update_action_for_submission_participant(recid, current_user.get_id(), 'uploader')
            return redirect(redirect_url.format(recid))
    else:
        return render_template('hepdata_records/error_page.html', recid=recid,
                               message="Incorrect file type uploaded.",
                               errors={"Submission": [{"level": "error",
                                                       "message": "You must upload a .zip, .tar, or .tar.gz file."}]})


def process_zip_archive(file, id):
    filename = secure_filename(file.filename)
    time_stamp = str(int(round(time.time())))
    file_save_directory = os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp)

    if not os.path.exists(file_save_directory):
        os.makedirs(file_save_directory)

    if '.oldhepdata' not in filename:
        file_path = os.path.join(file_save_directory, filename)
        file.save(file_path)

        submission_path = os.path.join(file_save_directory, remove_file_extension(filename))
        if 'yaml' in filename:
            # we split the singular yaml file and create a submission directory

            split_files(file_path, submission_path)
        else:
            # we are dealing with a zip, tar, etc. so we extract the contents
            extract(filename, file_path, submission_path)

        submission_found = find_file_in_directory(submission_path,
                                                  lambda x: x == "submission.yaml")
    else:
        file_path = os.path.join(file_save_directory, 'oldhepdata')
        if not os.path.exists(file_path):
            os.makedirs(file_path)

        if filename.endswith('.txt'):
            filename = filename.replace(".txt", "")
        print('Saving file to {}'.format(os.path.join(file_path, filename)))
        file.save(os.path.join(file_path, filename))

        submission_path = os.path.join(file_save_directory, 'oldhepdata')
        submission_found = False

    if submission_found:
        basepath, submission_file_path = submission_found
    else:
        result = check_and_convert_from_oldhepdata(submission_path, id,
                                                   time_stamp)

        # Check for errors
        if type(result) == dict:
            return result
        else:
            basepath, submission_file_path = result

    return process_submission_directory(basepath, submission_file_path, id)


def check_and_convert_from_oldhepdata(input_directory, id, timestamp):
    """ Check if the input directory contains a .oldhepdata file
    and convert it to YAML if it happens. """
    converted_path = os.path.join(current_app.config['CFG_DATADIR'], str(id), timestamp, 'yaml')
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
    successful = convert_oldhepdata_to_yaml(oldhepdata_found[1],
                                            converted_path)
    if not successful:
        return {
            "Converter": [{
                "level": "error",
                "message": "The conversion from oldhepdata "
                           "to the YAML format has not succeeded. "
                           "Please submit archives in the new format."
            }]
        }

    return find_file_in_directory(
        converted_path,
        lambda x: x == "submission.yaml"
    )


def query_messages_for_data_review(data_review_record, messages):
    if data_review_record.messages:
        data_messages = data_review_record.messages
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

    if current_user.is_authenticated:
        user_id = current_user.get_id()
        participant_records = SubmissionParticipant.query.filter_by(
            user_account=user_id, publication_recid=recid).all()

        for participant_record in participant_records:
            if participant_record is not None:
                if participant_record.role == 'reviewer':
                    ctx['show_review_widget'] = True

                if participant_record.role == 'uploader':
                    ctx['show_upload_widget'] = True

        user = User.query.get(current_user.get_id())
        if has_role(user, 'admin'):
            ctx['is_submission_coordinator_or_admin'] = True
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
