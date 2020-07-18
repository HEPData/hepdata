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

"""Blueprint for HEPData-Records."""

import logging
import json
import time
from dateutil import parser
from invenio_accounts.models import User
from flask_login import login_required, login_user
from flask import Blueprint, send_file, abort, redirect
from flask_security.utils import verify_password
from sqlalchemy import or_, func
import yaml
try:
    from yaml import CBaseLoader as Loader
except ImportError:  # pragma: no cover
    from yaml import BaseLoader as Loader  # pragma: no cover

from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE, SITE_URL
from hepdata.ext.elasticsearch.api import get_records_matching_field, get_count_for_collection, get_n_latest_records, \
    index_record_ids
from hepdata.modules.email.api import send_new_upload_email, send_new_review_message_email, NoReviewersException, \
    send_question_email
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.records.api import request, determine_user_privileges, render_template, format_submission, \
    render_record, current_user, db, jsonify, get_user_from_id, get_record_contents, extract_journal_info, \
    user_allowed_to_perform_action, NoResultFound, OrderedDict, query_messages_for_data_review, returns_json, \
    process_payload
from hepdata.modules.submission.models import HEPSubmission, DataSubmission, \
    DataResource, DataReview, Message, Question
from hepdata.modules.records.utils.common import get_record_by_id, \
    default_time, IMAGE_TYPES, decode_string
from hepdata.modules.records.utils.data_processing_utils import \
    generate_table_structure
from hepdata.modules.records.utils.submission import create_data_review, \
    get_or_create_hepsubmission
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.workflow import \
    update_action_for_submission_participant
from hepdata.modules.stats.views import increment
from hepdata.modules.permissions.models import SubmissionParticipant

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint(
    'hepdata_records',
    __name__,
    url_prefix='/record',
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)


@blueprint.route('/sandbox/<int:id>', methods=['GET'])
def sandbox_display(id):

    hepdata_submission = HEPSubmission.query.filter(
        HEPSubmission.publication_recid == id,
        or_(HEPSubmission.overall_status == 'sandbox',
            HEPSubmission.overall_status == 'sandbox_processing')).first()

    if hepdata_submission is not None:
        if hepdata_submission.overall_status == 'sandbox_processing':
            ctx = {'recid': id}
            determine_user_privileges(id, ctx)
            return render_template('hepdata_records/publication_processing.html', ctx=ctx)
        else:
            ctx = format_submission(id, None, 1, 1, hepdata_submission)
            ctx['mode'] = 'sandbox'
            ctx['show_review_widget'] = False
            increment(id)
            return render_template('hepdata_records/sandbox.html', ctx=ctx)

    else:
        return render_template('hepdata_records/error_page.html', recid=None,
                               message="No submission exists with that ID.",
                               errors={})


@blueprint.route('/<string:recid>', methods=['GET'], strict_slashes=True)
def get_metadata_by_alternative_id(recid):

    try:
        if "ins" in recid:
            recid = recid.replace("ins", "")
            record = get_records_matching_field('inspire_id', recid,
                                                doc_type=CFG_PUB_TYPE)
            record = record['hits']['hits'][0].get("_source")
            try:
                version = int(request.args.get('version', -1))
            except ValueError:
                version = -1

            output_format = request.args.get('format', 'html')
            light_mode = bool(request.args.get('light', False))

            return render_record(recid=record['recid'], record=record, version=version, output_format=output_format,
                                 light_mode=light_mode)
        else:
            log.error("Unable to find %s.", recid)
            return abort(404)

    except Exception as e:
        log.error("Unable to find %s.", recid)
        log.error(e)
        return abort(404)


@blueprint.route('/question/<int:recid>', methods=['POST'])
@login_required
def submit_question(recid):
    question = request.form['question']
    try:
        question = Question(user=int(current_user.get_id()), publication_recid=recid, question=str(question))
        db.session.add(question)
        db.session.commit()
        send_question_email(question)
    except Exception as e:
        log.error(e)
        db.session.rollback()

    return jsonify({'status': 'queued', 'message': 'Your question has been posted.'})


@blueprint.route('/<int:recid>/<int:version>/notify', methods=['POST'], strict_slashes=True)
@login_required
def notify_reviewers(recid, version):
    message = request.form['message']

    submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).first()
    try:
        current_user_obj = get_user_from_id(current_user.get_id())
        send_new_upload_email(recid, current_user_obj, message=message)

        submission.reviewers_notified = True
        db.session.add(submission)
        db.session.commit()

        return jsonify({"status": "success"})
    except NoReviewersException:
        return jsonify({"status": "error", "message": "There are no reviewers for this submission."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": e.__str__()})


@blueprint.route('/<int:recid>/metadata', methods=['GET', 'POST'])
@blueprint.route('/<int:recid>/', methods=['GET', 'POST'])
@blueprint.route('/<int:recid>', methods=['GET', 'POST'])
def metadata(recid):
    """
    Queries and returns a data record.

    :param recid: the record id being queried
    :return: renders the record template
    """

    try:
        version = int(request.args.get('version', -1))
    except ValueError:
        version = -1
    serialization_format = request.args.get('format', 'html')
    light_mode = bool(request.args.get('light', False))

    try:
        record = get_record_contents(recid)
    except Exception as e:
        record = None

    return render_record(recid=recid, record=record, version=version, output_format=serialization_format,
                         light_mode=light_mode)


@blueprint.route('/count')
def get_count_stats():
    pub_count = get_count_for_collection(CFG_PUB_TYPE)
    data_count = get_count_for_collection(CFG_DATA_TYPE)

    return jsonify(
        {"data": data_count['count'], "publications": pub_count["count"]})


@blueprint.route('/latest')
def get_latest():
    """
    Returns the N latest records from the database.

    :param n:
    :return:
    """
    n = int(request.args.get('n', 3))
    latest_records = get_n_latest_records(n)
    result = {"latest": []}
    for record in latest_records:
        record_information = record['_source']
        if 'recid' in record_information:

            last_updated = record_information['creation_date']

            if "last_updated" in record_information:
                last_updated = record_information["last_updated"]
                last_updated = parser.parse(last_updated).strftime("%Y-%m-%d")

            extract_journal_info(record_information)
            record_information['author_count'] = len(record_information.get('summary_authors', []))
            record_information['last_updated'] = last_updated
            result['latest'].append(record_information)

    return jsonify(result)


@blueprint.route('/data/<int:recid>/<int:data_recid>/<int:version>', methods=['GET', ])
def get_table_details(recid, data_recid, version):
    """
    Get the table details.

    :param recid:
    :param data_recid:
    :param version:
    :return:
    """

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

            attempts = 0
            while True:
                try:
                    with open(file_location, 'r') as table_file:
                        table_contents = yaml.load(table_file, Loader=Loader)
                except:
                    attempts += 1
                # allow multiple attempts to read file in case of temporary disk problems
                if (table_contents and table_contents is not None) or attempts > 5:
                    break

            table_contents["name"] = datasub_record.name
            table_contents["title"] = datasub_record.description
            table_contents["keywords"] = datasub_record.keywords
            table_contents["doi"] = datasub_record.doi
            table_contents["location"] = datasub_record.location_in_publication

        # we create a map of files mainly to accommodate the use of thumbnails for images where possible.
        tmp_assoc_files = {}
        for associated_data_file in datasub_record.resources:
            alt_location = associated_data_file.file_location
            location_parts = alt_location.split('/')

            key = location_parts[-1].replace("thumb_", "")
            if key not in tmp_assoc_files:
                tmp_assoc_files[key] = {}

            if "thumb_" in alt_location and associated_data_file.file_type.lower() in IMAGE_TYPES:
                tmp_assoc_files[key]['preview_location'] = '/record/resource/{0}?view=true'.format(
                    associated_data_file.id)
            else:
                tmp_assoc_files[key].update({'description': associated_data_file.file_description,
                                             'type': associated_data_file.file_type,
                                             'id': associated_data_file.id,
                                             'alt_location': alt_location})

        # add associated files to the table contents
        table_contents['associated_files'] = list(tmp_assoc_files.values())

    table_contents["review"] = {}

    data_review_record = create_data_review(data_recid, recid, version)
    table_contents["review"]["review_flag"] = data_review_record.status if data_review_record else "todo"
    table_contents["review"]["messages"] = len(data_review_record.messages) > 0 if data_review_record else False

    # translate the table_contents to an easy to render format of the qualifiers (with colspan),
    # x and y headers (should not require a colspan)
    # values, that also encompass the errors

    return jsonify(generate_table_structure(table_contents))


@blueprint.route('/coordinator/view/<int:recid>', methods=['GET', ])
@login_required
def get_coordinator_view(recid):
    """
    Returns the coordinator view for a record.

    :param recid:
    """
    hepsubmission_record = get_latest_hepsubmission(publication_recid=recid)

    participants = {"reviewer": {"reserve": [], "primary": []},
                    "uploader": {"reserve": [], "primary": []}}

    for participant in hepsubmission_record.participants:
        if participant.role in participants:
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
    recid = int(request.form['publication_recid'])
    data_id = int(request.form['data_recid'])
    status = request.form['status']
    version = int(request.form['version'])

    if user_allowed_to_perform_action(recid):

        record_sql = DataReview.query.filter_by(data_recid=data_id,
                                                version=version)
        try:
            record = record_sql.first()
        except NoResultFound:
            record = create_data_review(data_id, recid, version)

        record_sql.update({"status": status}, synchronize_session='fetch')
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify(
            {"recid": record.publication_recid, "data_id": record.data_recid,
             "status": record.status})

    return jsonify(
        {"recid": recid, "data_id": data_id, 'message': 'You are not authorised to update the review status for '
                                                        'this data record.'})


@blueprint.route('/data/review/', methods=['GET', ])
def get_data_reviews_for_record():
    """
    Get the data reviews for a record.

    :return: json response with reviews (or a json with an error key if not)
    """
    recid = int(request.args.get('publication_recid'))
    record_sql = DataReview.query.filter_by(publication_recid=recid)

    if user_allowed_to_perform_action(recid):
        try:
            records = record_sql.all()
            record_result = []
            for record in records:
                record_result.append(
                    {"data_recid": record.data_recid, "status": record.status,
                     "last_updated": record.modification_date})

            return json.dumps(record_result, default=default_time)
        except:
            return jsonify({"error": "no reviews found"})


@blueprint.route('/data/review/status/', methods=['GET', ])
def get_data_review_status():
    data_id = request.args.get('data_recid')

    record_sql = DataReview.query.filter_by(data_recid=data_id)

    try:
        record = record_sql.one()
        return jsonify(
            {"publication_recid": record.publication_recid,
             "data_recid": record.data_recid, "status": record.status})
    except:
        return jsonify({"error": "no review found."})


@blueprint.route(
    '/data/review/message/<int:publication_recid>/<int:data_recid>',
    methods=['POST', ])
@login_required
def add_data_review_messsage(publication_recid, data_recid):
    """
    Adds a new review message for a data submission.

    :param publication_recid:
    :param data_recid:
    """

    trace = []
    message = request.form.get('message', '')
    version = request.form['version']
    userid = current_user.get_id()

    try:
        datareview_query = DataReview.query.filter_by(data_recid=data_recid,
                                                      version=version)

        # if the data review is not already created, create one.
        try:
            data_review_record = datareview_query.one()
            trace.append("adding data review record")
        except:
            data_review_record = create_data_review(data_recid, publication_recid)
            trace.append("created a new data review record")

        data_review_message = Message(user=userid, message=message)
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
             "message": decode_string(data_review_message.message),
             "post_time": data_review_message.creation_date,
             'user': current_user_obj.email}, default=default_time)
    except Exception as e:
        db.session.rollback()
        raise e


@blueprint.route(
    '/data/review/message/<int:data_recid>/<int:version>',
    methods=['GET', ])
@login_required
def get_review_messages_for_data_table(data_recid, version):
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
    """
    Gets the review messages for a publication id.

    :param publication_recid:
    :return:
    """
    messages = OrderedDict()

    latest_submission = get_latest_hepsubmission(publication_recid=publication_recid)

    datareview_query = DataReview.query.filter_by(
        publication_recid=publication_recid, version=latest_submission.version).order_by(
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


@blueprint.route('/resources/<int:recid>/<int:version>', methods=['GET'])
@returns_json
def get_resources(recid, version):
    """
    Gets a list of resources for a publication, relevant to all data records.

    :param recid:
    :return: json
    """
    result = {'submission_items': []}
    common_resources = {'name': 'Common Resources', 'type': 'submission', 'version': version, 'id': recid,
                        'resources': []}
    submission = get_latest_hepsubmission(publication_recid=recid, version=version)

    if submission:
        for reference in submission.resources:
            common_resources['resources'].append(process_resource(reference))

    result['submission_items'].append(common_resources)

    datasubmissions = DataSubmission.query.filter_by(publication_recid=recid, version=version).\
        order_by(DataSubmission.id.asc()).all()

    for datasubmission in datasubmissions:
        submission_item = {'name': datasubmission.name, 'type': 'data', 'id': datasubmission.id, 'resources': [],
                           'version': datasubmission.version}
        for reference in datasubmission.resources:
            submission_item['resources'].append(process_resource(reference))

        result['submission_items'].append(submission_item)
    return json.dumps(result)


def process_resource(reference):
    """
    For a submission resource, create the link to the location, or the image file if an image.

    :param reference:
    :return: dict
    """
    _location = '/record/resource/{0}?view=true'.format(reference.id)

    if 'http' in reference.file_location:
        _location = reference.file_location

    _reference_data = {'id': reference.id, 'file_type': reference.file_type,
                       'file_description': reference.file_description,
                       'location': _location}

    if reference.file_type.lower() in IMAGE_TYPES:
        _reference_data['preview_location'] = _location

    return _reference_data


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
            if resource_obj.file_type.lower() not in IMAGE_TYPES:
                print("Resource is at: " + resource_obj.file_location)
                with open(resource_obj.file_location, 'r') as resource_file:
                    contents = resource_file.read()
                    # Don't return file contents if they contain a null byte.
                    if '\0' in contents:
                        contents = 'Binary'

            return jsonify(
                {"location": '/record/resource/{0}?view=true'.format(resource_obj.id), 'type': resource_obj.file_type,
                 'description': resource_obj.file_description, 'file_contents': decode_string(contents)})

    else:
        log.error("Unable to find resource %d.", resource_id)
        return abort(404)


@blueprint.route('/cli_upload', methods=['GET', 'POST'])
def cli_upload():
    """
    Used by the hepdata-cli tool to upload a submission.

    :return:
    """

    if request.method == 'GET':
        return redirect('/')

    # email must be provided
    if 'email' not in request.form.keys():
        return jsonify({"message": "User email is required: specify one using -e user-email."}), 400
    user_email = request.form['email']

    # password must be provided
    if 'pswd' not in request.form.keys():
        return jsonify({"message": "User password is required."}), 400
    user_pswd = request.form['pswd']

    # check user associated with this email exists and is active with a confirmed email address
    user = User.query.filter(func.lower(User.email) == user_email.lower(), User.active.is_(True), User.confirmed_at.isnot(None)).first()
    if user is None:
        return jsonify({"message": "Email {} does not match an active confirmed user.".format(user_email)}), 404
    elif user.password is None:
        return jsonify({"message": "Set HEPData password from {} first.".format(SITE_URL + '/lost-password/')}), 403
    elif verify_password(user_pswd, user.password) is False:
        return jsonify({"message": "Wrong password, please try again."}), 403
    else:
        login_user(user)

    # sandbox must be provided
    if 'sandbox' not in request.form.keys():
        return jsonify({"message": "sandbox (True or False) is required."}), 400
    str_sandbox = request.form['sandbox']
    is_sandbox = False if str_sandbox == 'False' else True if str_sandbox == 'True' else None

    recid = request.form['recid'] if 'recid' in request.form.keys() else None
    invitation_cookie = request.form['invitation_cookie'] if 'invitation_cookie' in request.form.keys() else None

    if is_sandbox is True:
        if recid is None:
            return consume_sandbox_payload()  # '/sandbox/consume'
        else:
            # check that sandbox record exists and belongs to this user
            hepsubmission_record = get_latest_hepsubmission(publication_recid=recid, overall_status='sandbox')
            if hepsubmission_record is None:
                return jsonify({"message": "Sandbox record {} not found.".format(str(recid))}), 404
            elif hepsubmission_record.coordinator != user.id:
                return jsonify({"message": "Attempted to modify sandbox record of another user."}), 403
            else:
                return update_sandbox_payload(recid)  # '/sandbox/<int:recid>/consume'
    elif is_sandbox is False:
        # check that record exists and has 'todo' status
        hepsubmission_record = get_latest_hepsubmission(publication_recid=recid, overall_status='todo')
        if hepsubmission_record is None:
            return jsonify({"message": "Record {} not found.".format(str(recid))}), 404
        # check user is allowed to upload to this record and supplies the correct invitation cookie
        participant = SubmissionParticipant.query.filter_by(user_account=user.id, role='uploader', publication_recid=recid, status='primary').first()
        if participant is None:
            return jsonify({"message": "Email {} does not correspond to a confirmed uploader for this record.".format(str(user_email))}), 404
        elif str(participant.invitation_cookie) != invitation_cookie:
            return jsonify({"message": "Invitation cookie did not match."}), 403
        return consume_data_payload(recid)  # '/<int:recid>/consume'


@blueprint.route('/<int:recid>/consume', methods=['GET', 'POST'])
@login_required
def consume_data_payload(recid):
    """
    This method persists, then presents the loaded data back to the user.

    :param recid: record id to attach the data to
    :return: For POST requests, returns JSONResponse either containing 'url'
             (for success cases) or 'message' (for error cases, which will
             give a 400 error). For GET requests, redirects to the record.
    """

    if request.method == 'POST':
        file = request.files['hep_archive']
        redirect_url = request.url_root + "record/{}"
        return process_payload(recid, file, redirect_url)

    else:
        return redirect('/record/' + str(recid))


@blueprint.route('/sandbox', methods=['GET'])
@login_required
def sandbox():
    current_id = current_user.get_id()
    submissions = HEPSubmission.query.filter(
        HEPSubmission.coordinator == current_id,
        or_(HEPSubmission.overall_status == 'sandbox',
            HEPSubmission.overall_status == 'sandbox_processing')
    ).order_by(HEPSubmission.last_updated.desc()).all()

    for submission in submissions:
        submission.data_abstract = submission.data_abstract

    return render_template('hepdata_records/sandbox.html',
                           ctx={"submissions": submissions})


@blueprint.route('/attach_information/<int:recid>', methods=['POST'])
@login_required
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
    if record is not None and status == 'success':
        content['recid'] = recid
        record.update(content)
        record.commit()

        hep_submission = HEPSubmission.query.filter_by(
            publication_recid=recid, overall_status="todo").first()
        hep_submission.inspire_id = inspire_id
        db.session.add(hep_submission)

        db.session.commit()

        return jsonify({'status': 'success'})

    elif status != 'success':
        return jsonify({'status': status,
                        'message': 'Request for INSPIRE record {} failed.'.format(inspire_id)})

    else:
        return jsonify({'status': 'failed',
                        'message': 'No record with recid {} was found.'.format(str(recid))})


@blueprint.route('/sandbox/consume', methods=['GET', 'POST'])
@login_required
def consume_sandbox_payload():
    """
    Creates a new sandbox submission with a new file upload.

    :param recid:
    """

    if request.method == 'GET':
        return redirect('/record/sandbox')

    id = (int(current_user.get_id())) + int(round(time.time()))

    get_or_create_hepsubmission(id, current_user.get_id(), status="sandbox")
    file = request.files['hep_archive']
    redirect_url = request.url_root + "record/sandbox/{}"
    return process_payload(id, file, redirect_url)


@blueprint.route('/sandbox/<int:recid>/consume', methods=['GET', 'POST'])
@login_required
def update_sandbox_payload(recid):
    """
    Updates the Sandbox submission with a new file upload.

    :param recid:
    """

    if request.method == 'GET':
        return redirect('/record/sandbox/' + str(recid))

    file = request.files['hep_archive']
    redirect_url = request.url_root + "record/sandbox/{}"
    return process_payload(recid, file, redirect_url)


@blueprint.route('/add_resource/<string:type>/<int:identifier>/<int:version>', methods=['POST'])
@login_required
def add_resource(type, identifier, version):
    """
    Adds a data resource to either the submission or individual data files.

    :param type:
    :param identifier:
    :param version:
    :return:
    """

    submission = None
    inspire_id = None
    recid = None

    if type == 'submission':
        submission = HEPSubmission.query.filter_by(publication_recid=identifier, version=version).one()
        if submission:
            inspire_id = submission.inspire_id
            recid = submission.publication_recid

    elif type == 'data':
        submission = DataSubmission.query.filter_by(id=identifier).one()
        if submission:
            inspire_id = submission.publication_inspire_id
            recid = submission.publication_recid

    if not user_allowed_to_perform_action(recid):
        abort(403)

    analysis_type = request.form.get('analysisType', None)
    analysis_other = request.form.get('analysisOther', None)
    analysis_url = request.form.get('analysisURL', None)
    analysis_description = request.form.get('analysisDescription', None)

    if analysis_type == 'other':
        analysis_type = analysis_other

    if analysis_type and analysis_url:

        if submission:
            new_resource = DataResource(file_location=analysis_url, file_type=analysis_type,
                                        file_description=str(analysis_description))

            submission.resources.append(new_resource)

            try:
                db.session.add(submission)
                db.session.commit()

                try:
                    index_record_ids([recid])
                except:
                    log.error('Failed to reindex {0}'.format(recid))

                if inspire_id:
                    return redirect('/record/ins{0}'.format(inspire_id))
                else:
                    return redirect('/record/{0}'.format(recid))
            except Exception as e:
                db.session.rollback()
                raise e

    return render_template('hepdata_records/error_page.html', recid=None,
                           header_message='Error adding resource.',
                           message='Unable to add resource. Please try again.',
                           errors={})
