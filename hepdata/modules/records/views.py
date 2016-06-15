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

"""Blueprint for HEPData-Records."""

from __future__ import absolute_import, print_function
from collections import OrderedDict
from functools import wraps
import json
import os
from dateutil import parser
from flask.ext.login import login_required, current_user
from flask import Blueprint, redirect, request, render_template, Response, \
    jsonify, send_file, current_app
from invenio_accounts.models import User
from invenio_db import db
import jsonpatch
from sqlalchemy.orm.exc import NoResultFound
import time
from werkzeug.utils import secure_filename
import yaml
from hepdata.config import CFG_PUB_TYPE, CFG_DATA_TYPE
from hepdata.ext.elasticsearch.api import get_records_matching_field, \
    get_record, get_count_for_collection, get_n_latest_records
from hepdata.modules.converter import convert_oldhepdata_to_yaml
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.records.models import HEPSubmission, DataSubmission, \
    DataResource, DataReview, DataReviewMessage, SubmissionParticipant, \
    RecordVersionCommitMessage
from hepdata.modules.records.utils.common import get_record_by_id, \
    default_time, allowed_file, \
    find_file_in_directory, decode_string, \
    truncate_string, IMAGE_TYPES, remove_file_extension
from hepdata.modules.records.utils.data_processing_utils import \
    generate_table_structure, process_ctx
from hepdata.modules.records.utils.submission import create_data_review, \
    get_or_create_hepsubmission, process_submission_directory, remove_submission
from hepdata.modules.records.utils.users import get_coordinators_in_system, \
    has_role
from hepdata.modules.records.utils.workflow import \
    update_action_for_submission_participant, send_new_upload_email
from hepdata.modules.records.utils.workflow import \
    send_new_review_message_email
from hepdata.modules.stats.views import get_count, increment
from hepdata.utils.file_extractor import extract

blueprint = Blueprint(
    'hepdata_records',
    __name__,
    url_prefix='/record',
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)

RECORD_PLAIN_TEXT = {
    "passed": "passed review",
    "attention": "attention required",
    "todo": "to be reviewed"
}


@login_required
@blueprint.route('/sandbox/<int:id>', methods=['GET'])
def sandbox_display(id):
    hepdata_submission = HEPSubmission.query.filter_by(
        publication_recid=id).first()
    version = int(request.args.get('version', -1))

    if hepdata_submission is not None:
        ctx = format_submission(id, None, version, hepdata_submission)
        ctx['mode'] = 'sandbox'
        ctx['show_review_widget'] = False
        increment(id)
        return render_template('hepdata_records/sandbox.html', ctx=ctx)
    else:
        return render_template('hepdata_records/error_page.html', recid=None,
                               message="No submission exists with that ID.",
                               errors={})


@blueprint.route('/<string:recid>', methods=['GET'], strict_slashes=True)
def get_metadata_by_alternative_id(recid, *args, **kwargs):
    try:
        if "ins" in recid:
            recid = recid.replace("ins", "")
            record = get_records_matching_field('inspire_id', recid,
                                                doc_type=CFG_PUB_TYPE)
            record = record['hits']['hits'][0].get("_source")
            version = int(request.args.get('version', -1))

            output_format = request.args.get('format', 'html')
            light_mode = bool(request.args.get('light', False))

            return do_render_record(recid=record['recid'], record=record, version=version, output_format=output_format,
                                    light_mode=light_mode)
    except Exception as e:
        return render_template('hepdata_theme/404.html')


def get_record_contents(recid):
    """
    Tries to get record from elastic search first. Failing that,
    it tries from the database.
    :param recid: Record ID to get.
    :return: a dictionary containing the record contents if the recid exists,
    None otherwise.
    """
    record = get_record(recid, doc_type=CFG_PUB_TYPE)
    if record is None:
        record = get_record_by_id(recid)

    return record


@blueprint.route('/<int:recid>/metadata', methods=['GET', 'POST'])
@blueprint.route('/<int:recid>/', methods=['GET', 'POST'])
@blueprint.route('/<int:recid>', methods=['GET', 'POST'])
def metadata(recid, *args, **kwargs):
    """
    Queries and returns a data record
    :param recid: the record id being queried
    :param args:
    :param kwargs:
    :return: renders the record template
    """
    version = int(request.args.get('version', -1))
    format = request.args.get('format', 'html')

    try:
        record = get_record_contents(recid)
    except Exception as e:
        record = None

    if record is None:
        return render_template('hepdata_theme/404.html')

    return do_render_record(recid=recid, record=record, version=version, output_format=format)


def format_submission(recid, record, version, hepdata_submission,
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
        ctx["version_count"] = hepdata_submission.latest_version

        if version is not -1:
            ctx["version"] = version
        else:
            ctx["version"] = hepdata_submission.latest_version

        if record is not None:
            if "collaborations" in record and type(record['collaborations']) is not list:
                collaborations = [x.strip() for x in record["collaborations"].split(",")]
                ctx['record']['collaborations'] = collaborations

            authors = record.get('authors', None)
            if "first_author" in record and 'full_name' in record["first_author"]:
                ctx['breadcrumb_text'] = record["first_author"]["full_name"]
                if authors is not None and len(record['authors']) > 1:
                    ctx['breadcrumb_text'] += " et al."

            try:
                commit_message_query = RecordVersionCommitMessage.query \
                    .filter_by(version=ctx["version"], recid=recid).one()

                ctx["revision_message"] = {
                    'version': commit_message_query.version,
                    'message': commit_message_query.message}

            except NoResultFound:
                pass

            if authors:
                truncate_author_list(record)

            determine_user_privileges(recid, ctx)

        else:
            ctx['record'] = {}
            determine_user_privileges(recid, ctx)
            ctx['show_upload_widget'] = True
            ctx['show_review_widget'] = False

        ctx['record']['last_updated'] = hepdata_submission.last_updated

        ctx['record']['hepdata_doi'] = "{0}".format(hepdata_submission.doi)
        if ctx['version'] > 1:
            ctx['record']['hepdata_doi'] += ".v{0}".format(ctx['version'])

        ctx['recid'] = recid
        ctx["status"] = hepdata_submission.overall_status
        ctx['record']['data_abstract'] = decode_string(hepdata_submission.data_abstract)

        extract_journal_info(record)

        if hepdata_submission.overall_status != 'finished' and ctx["version_count"] > 0:

            if not (ctx['show_review_widget'] or ctx['show_upload_widget']
                    or ctx['is_submission_coordinator_or_admin']):
                # we show the latest approved version.
                ctx["version"] -= 1
                ctx["version_count"] -= 1

        ctx['additional_resources'] = len(hepdata_submission.references) > 0

        # query for a related data submission
        data_record_query = DataSubmission.query.filter_by(
            publication_recid=recid,
            version=ctx["version"]).order_by(DataSubmission.id.asc())

        first_data_id = -1
        data_table_metadata, first_data_id = process_data_tables(
            ctx, data_record_query, first_data_id, data_table)

        assign_or_create_review_status(data_table_metadata, recid,
                                       ctx["version"])

        ctx['table_to_show'] = first_data_id
        if 'table' in request.args:
            if request.args['table'] is not '':
                ctx['table_to_show'] = request.args['table']

        ctx['data_tables'] = data_table_metadata.values()
        ctx['access_count'] = get_count(recid)
        ctx['mode'] = 'record'
        ctx['coordinator'] = hepdata_submission.coordinator
        ctx['coordinators'] = get_coordinators_in_system()
        ctx['record'].pop('authors', None)

    return ctx


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


def do_render_record(recid, record, version, output_format, light_mode=False):
    hepdata_submission = HEPSubmission.query.filter_by(
        publication_recid=recid).first()

    if hepdata_submission is not None:
        ctx = format_submission(recid, record, version, hepdata_submission)
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

            hepdata_submission = HEPSubmission.query.filter_by(
                publication_recid=publication_recid).first()

            ctx = format_submission(publication_recid, publication_record,
                                    version, hepdata_submission,
                                    data_table=record['title'])
            ctx['related_publication_id'] = publication_recid
            ctx['table_name'] = record['title']

            if output_format == "json":
                ctx = process_ctx(ctx, light_mode)
                return jsonify(ctx)
            else:
                return render_template('hepdata_records/data_record.html', ctx=ctx)
        except:
            return render_template('hepdata_theme/404.html')


def returns_json(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        return Response(r, content_type='application/json; charset=utf-8')

    return decorated_function


@blueprint.route('/count')
def get_count_stats():
    pub_count = get_count_for_collection(CFG_PUB_TYPE)
    data_count = get_count_for_collection(CFG_DATA_TYPE)

    return jsonify(
        {"data": data_count['count'], "publications": pub_count["count"]})


@blueprint.route('/latest')
def get_latest():
    """
    Returns the N latest records from the database
    :param n:
    :return:
    """
    n = int(request.args.get('n', 3))

    latest_records = get_n_latest_records(n)

    result = {"latest": []}
    for record in latest_records:
        record_information = record['_source']
        if 'recid' in record_information:
            collaborations = []
            if 'collaborations' in record_information:
                collaborations = record_information['collaborations']

            last_updated = record_information['creation_date']
            if "last_updated" in record_information:
                last_updated = record_information["last_updated"]
                last_updated = parser.parse(last_updated).strftime("%Y-%m-%d")

            extract_journal_info(record_information)

            authors = record_information.get('authors', [])
            if authors is None:
                author_count = 0
            else:
                author_count = len(authors)
            result['latest'].append({
                'id': record_information['recid'],
                'inspire_id': record_information['inspire_id'],
                'title': record_information['title'],
                'collaborations': collaborations,
                'journal': record_information['journal_info'],
                'author_count': author_count,
                'first_author': record_information.get('first_author', None),
                'creation_date': record_information['creation_date'],
                'last_updated': last_updated})

    return jsonify(result)


@blueprint.route('/data/<int:recid>/<int:data_recid>/<int:version>',
                 methods=['GET', ])
def get_table_details(recid, data_recid, version):
    datasub_query = DataSubmission.query.filter_by(id=data_recid,
                                                   version=version)

    table_contents = {}

    if datasub_query.count() > 0:

        datasub_record = datasub_query.one()
        data_query = db.session.query(DataResource).filter(
            DataResource.id == datasub_record.data_file)

        if data_query.count() > 0:
            data_record = data_query.one()
            file_location = data_record.file_location

            table_contents = yaml.safe_load(file(file_location))
            table_contents["name"] = datasub_record.name
            table_contents["title"] = datasub_record.description
            table_contents["keywords"] = datasub_record.keywords
            table_contents["doi"] = datasub_record.doi

        # we create a map of files mainly to accommodate the use of thumbnails for images where possible.
        tmp_assoc_files = {}
        for associated_data_file in datasub_record.additional_files:
            alt_location = associated_data_file.file_location
            location_parts = alt_location.split('/')

            key = location_parts[-1].replace("thumb_", "")
            if key not in tmp_assoc_files:
                tmp_assoc_files[key] = {}

            if "thumb_" in alt_location:
                tmp_assoc_files[key]['preview_location'] = '/record/resource/{0}?view=true'.format(
                    associated_data_file.id)
            else:
                tmp_assoc_files[key].update({'description': associated_data_file.file_description,
                                             'type': associated_data_file.file_type,
                                             'id': associated_data_file.id,
                                             'alt_location': alt_location})

        # add associated files to the table contents
        table_contents['associated_files'] = tmp_assoc_files.values()

    table_contents["review"] = {}

    data_review_record = create_data_review(data_recid, recid, version)
    table_contents["review"]["review_flag"] = data_review_record.status
    table_contents["review"]["messages"] = len(data_review_record.messages) > 0

    # translate the table_contents to an easy to render format of the qualifiers (with colspan),
    # x and y headers (should not require a colspan)
    # values, that also encompass the errors

    return jsonify(generate_table_structure(table_contents))


@blueprint.route('/coordinator/view/<int:recid>', methods=['GET', ])
@login_required
def get_coordinator_view(recid):
    # there should only ever be one rev
    hepsubmission_record = db.session.query(HEPSubmission).filter(
        HEPSubmission.publication_recid == recid).one()

    participants = {"reviewer": {"reserve": [], "primary": []},
                    "uploader": {"reserve": [], "primary": []}}

    for participant in hepsubmission_record.participants:
        participants[participant.role][participant.status].append(
            {"full_name": participant.full_name, "email": participant.email,
             "id": participant.id})

    return json.dumps(
        {"recid": recid,
         "primary-reviewers": participants["reviewer"]["primary"],
         "reserve-reviewers": participants["reviewer"]["reserve"],
         "primary-uploaders": participants["uploader"]["primary"],
         "reserve-uploaders": participants["uploader"]["reserve"]})


@blueprint.route('/data/review/status/', methods=['POST', ])
@login_required
def set_data_review_status():
    # todo: need to check if the user is a reviewer for this record before being allowed to do this operation.

    # the recid is required to automatically create a review record if it doesn't already exist in the database.
    recid = int(request.form['publication_recid'])
    data_id = int(request.form['data_recid'])
    status = request.form['status']
    version = int(request.form['version'])

    record_sql = DataReview.query.filter_by(data_recid=data_id,
                                            version=version)
    try:
        record = record_sql.one()
    except NoResultFound:
        record = create_data_review(data_id, recid, version)

    record_sql.update({"status": status}, synchronize_session='fetch')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return json.dumps(
        {"recid": record.publication_recid, "data_id": record.data_recid,
         "status": record.status})


@blueprint.route('/data/review/', methods=['GET', ])
def get_data_reviews_for_record():
    # need to check if the user is a reviewer for this record before being allowed to do this operation.
    recid = int(request.args.get('publication_recid'))
    record_sql = DataReview.query.filter_by(publication_recid=recid)

    try:
        records = record_sql.all()
        record_result = []
        for record in records:
            record_result.append(
                {"data_recid": record.data_recid, "status": record.status,
                 "last_updated": record.modification_date})

        return json.dumps(record_result, default=default_time)
    except:
        return json.dumps({"error": "no reviews found"})


@blueprint.route('/data/review/status/', methods=['GET', ])
def get_data_review_status():
    data_id = request.args.get('data_recid')

    record_sql = DataReview.query.filter_by(data_recid=data_id)

    try:
        record = record_sql.one()
        return json.dumps(
            {"publication_recid": record.publication_recid,
             "data_recid": record.data_recid, "status": record.status})
    except:
        return json.dumps({"error": "no review found."})


@blueprint.route(
    '/data/review/message/<int:publication_recid>/<int:data_recid>',
    methods=['POST', ])
@login_required
def add_data_review_messsage(publication_recid, data_recid):
    # need to set up a session and query for the data review.

    trace = []
    message = request.form['message']
    version = request.form['version']
    userid = current_user.get_id()

    datareview_query = DataReview.query.filter_by(data_recid=data_recid,
                                                  version=version)

    # if the data review is not already created, create one.
    try:
        data_review_record = datareview_query.one()
        trace.append("adding data review record")
    except:
        data_review_record = create_data_review(data_recid, publication_recid)
        trace.append("created a new data review record")

    data_review_message = DataReviewMessage(user=userid, message=message)
    data_review_record.messages.append(data_review_message)

    db.session.commit()

    current_user_obj = get_user_from_id(userid)

    update_action_for_submission_participant(publication_recid, userid,
                                             'reviewer')
    send_new_review_message_email(data_review_record, data_review_message,
                                  current_user_obj)

    return json.dumps(
        {"publication_recid": data_review_record.publication_recid,
         "data_recid": data_review_record.data_recid,
         "status": data_review_record.status,
         "message": data_review_message.message,
         "post_time": data_review_message.creation_date,
         'user': current_user_obj.email}, default=default_time)


@blueprint.route(
    '/data/review/message/<int:publication_recid>/<int:data_recid>/<int:version>',
    methods=['GET', ])
@login_required
def get_review_messages_for_data_table(publication_recid, data_recid, version):
    datareview_query = DataReview.query.filter_by(data_recid=data_recid,
                                                  version=version)

    messages = []

    if datareview_query.count() > 0:
        data_review_record = datareview_query.one()
        query_messages_for_data_review(data_review_record, messages)

    else:
        return json.dumps({"error": "there are no messages!"})

    return json.dumps(messages, default=default_time)


@blueprint.route('/data/review/message/<int:publication_recid>',
                 methods=['GET', ])
@login_required
def get_all_review_messages(publication_recid):
    # stores messages by the data table they refer to.
    messages = OrderedDict()

    datareview_query = DataReview.query.filter_by(
        publication_recid=publication_recid).order_by(
        DataReview.id.asc())

    if datareview_query.count() > 0:
        reviews = datareview_query.all()

        for data_review in reviews:

            data_submission_query = DataSubmission.query.filter_by(
                id=data_review.data_recid)
            data_submission_record = data_submission_query.one()

            if data_review.data_recid not in messages:
                if data_submission_query.count() > 0:
                    messages[data_submission_record.name] = []

            query_messages_for_data_review(data_review, messages[
                data_submission_record.name])

    return json.dumps(messages, default=default_time)


@blueprint.route('/resources/<int:recid>', methods=['GET'])
@returns_json
def get_resources(recid):
    """
    Gets a list of resources for a publication, relevant to all data records
    :param recid:
    :return: json
    """
    result = []
    submission = HEPSubmission.query.filter_by(publication_recid=recid)
    if submission.count() > 0:
        submission_obj = submission.first()
        for reference in submission_obj.references:
            result.append(
                {'id': reference.id, 'file_type': reference.file_type,
                 'file_description': reference.file_description,
                 'location': reference.file_location})

    return json.dumps(result)


@blueprint.route('/resource/<int:resource_id>', methods=['GET'])
def get_resource(resource_id):
    """
    Attempts to find any HTML resources to be displayed for a record in the event that it
    does not have proper data records included.
    :param recid: publication record id
    :return: json dictionary containing any HTML files to show.
    """

    resource = DataResource.query.filter_by(id=resource_id)
    view_mode = bool(request.args.get('view', False))

    if resource.count() > 0:
        resource_obj = resource.first()

        if view_mode:
            return send_file(resource_obj.file_location, as_attachment=True)
        elif 'html' in resource_obj.file_location and 'http' not in resource_obj.file_location:
            with open(resource_obj.file_location, 'r') as resource_file:
                html = resource_file.read()
                return html
        else:
            contents = ''
            if resource_obj.file_type not in IMAGE_TYPES:
                print("Resource is at: " + resource_obj.file_location)
                with open(resource_obj.file_location, 'r') as resource_file:
                    contents = resource_file.read()

                print("File contents are " + contents)

            return jsonify(
                {"location": '/record/resource/{0}?view=true'.format(resource_obj.id), 'type': resource_obj.file_type,
                 'description': resource_obj.file_description, 'file_contents': contents})


@blueprint.route('/<int:recid>/consume', methods=['GET', 'POST'])
def consume_data_payload(recid):
    # this method will persist, then present back the loaded data to the user via JSON.
    """
        This method persists, then presents the loaded data back to the user.
        :param recid: record Id to attach the data to
        :return: page rendering
    """

    if request.method == 'POST':
        file = request.files['hep_archive']
        return process_payload(recid, file, '/record/{}')

    else:
        return redirect('/record/' + str(recid))


@blueprint.route('/sandbox', methods=['GET'])
@login_required
def sandbox():
    current_id = current_user.get_id()
    submissions = HEPSubmission.query.filter_by(coordinator=current_id,
                                                overall_status='sandbox').all()
    return render_template('hepdata_records/sandbox.html',
                           ctx={"submissions": submissions})


@login_required
@blueprint.route('/attach_information/<int:recid>', methods=['POST'])
def attach_information_to_record(recid):
    """
    Given an INSPIRE data representation, this will process the data, and update information
    for a given record id with the contents.
    :return:
    """

    inspire_id = request.form['inspire_id']

    content, status = get_inspire_record_information(inspire_id)
    content["inspire_id"] = inspire_id

    record = get_record_by_id(recid)
    if record is not None:

        # TODO: Fix this to update the record information
        content['recid'] = recid

        patch = jsonpatch.JsonPatch.from_diff(record, content)
        record = record.patch(patch=patch)
        record.commit()
        db.session.commit()

        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'failed',
                        'message': 'No record with that recid was found.'})


@login_required
@blueprint.route('/sandbox/consume', methods=['POST'])
def consume_sandbox_payload():
    # generate a unique id
    import time

    id = (int(current_user.get_id())) + int(round(time.time()))

    get_or_create_hepsubmission(id, current_user.get_id(), status="sandbox")
    file = request.files['hep_archive']
    return process_payload(id, file, '/record/sandbox/{}', send_email=False)


@login_required
@blueprint.route('/sandbox/<int:recid>/consume', methods=['POST'])
def update_sandbox_payload(recid):
    # generate a unique id

    file = request.files['hep_archive']
    return process_payload(recid, file, '/record/sandbox/{}', send_email=False)


def process_payload(recid, file, redirect_url, send_email=True):
    print(file.filename)
    if file and (allowed_file(file.filename) or "oldhepdata" in file.filename):
        errors = process_zip_archive(file, recid)
        if errors:
            remove_submission(recid)
            return render_template('hepdata_records/error_page.html',
                                   recid=None, errors=errors)
        else:
            current_user_obj = get_user_from_id(current_user.get_id())
            update_action_for_submission_participant(recid, current_user.get_id(), 'uploader')
            if send_email:
                send_new_upload_email(recid, current_user_obj)
            return redirect(redirect_url.format(recid))
    else:
        return render_template('hepdata_records/error_page.html', recid=recid,
                               message="Incorrect file type uploaded.",
                               errors={"Submission": [{"level": "error",
                                                       "message": "You must upload a .zip, .tar, or .tar.gz file."}]})


def process_zip_archive(file, id):
    filename = secure_filename(file.filename)
    time_stamp = str(int(round(time.time())))
    if not os.path.exists(os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp)):
        os.makedirs(os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp))

    if '.oldhepdata' not in filename:
        file_path = os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp, filename)
        file.save(file_path)

        unzipped_path = os.path.join(current_app.config['CFG_DATADIR'],
                                     str(id), time_stamp, remove_file_extension(filename))
        extract(filename, file_path, unzipped_path)
        submission_found = find_file_in_directory(unzipped_path,
                                                  lambda x: x == "submission.yaml")
    else:
        file_path = os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp, 'oldhepdata')
        if not os.path.exists(file_path):
            os.makedirs(file_path)

        if filename.endswith('.txt'):
            filename = filename.replace(".txt", "")
        print('Saving file to {}'.format(os.path.join(file_path, filename)))
        file.save(os.path.join(file_path, filename))

        unzipped_path = os.path.join(current_app.config['CFG_DATADIR'], str(id), time_stamp, 'oldhepdata')
        submission_found = False

    if submission_found:
        basepath, submission_file_path = submission_found
    else:
        result = check_and_convert_from_oldhepdata(unzipped_path, id,
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


def get_user_from_id(userid):
    user_query = db.session.query(User).filter(User.id == userid)
    if user_query.count() > 0:
        return user_query.one()
    else:
        return None


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


def truncate_author_list(record):
    record['authors'] = record['authors'][:10]
