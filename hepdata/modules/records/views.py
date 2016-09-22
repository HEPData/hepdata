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

import logging
import json
from dateutil import parser
from flask.ext.login import login_required
from flask import Blueprint, send_file
import jsonpatch
import yaml
from invenio_db import db

from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE
from hepdata.ext.elasticsearch.api import get_records_matching_field, get_count_for_collection, get_n_latest_records
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.records.api import *
from hepdata.modules.submission.models import HEPSubmission, DataSubmission, \
    DataResource, DataReview, Message
from hepdata.modules.records.utils.common import get_record_by_id, \
    default_time, IMAGE_TYPES
from hepdata.modules.records.utils.data_processing_utils import \
    generate_table_structure
from hepdata.modules.records.utils.submission import create_data_review, \
    get_or_create_hepsubmission, get_latest_hepsubmission
from hepdata.modules.records.utils.workflow import \
    update_action_for_submission_participant, send_new_upload_email, NoReviewersException
from hepdata.modules.records.utils.workflow import \
    send_new_review_message_email
from hepdata.modules.stats.views import increment

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


@login_required
@blueprint.route('/sandbox/<int:id>', methods=['GET'])
def sandbox_display(id):
    hepdata_submission = HEPSubmission.query.filter_by(
        publication_recid=id).first()

    if hepdata_submission is not None:
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
            version = int(request.args.get('version', -1))

            output_format = request.args.get('format', 'html')
            light_mode = bool(request.args.get('light', False))

            return render_record(recid=record['recid'], record=record, version=version, output_format=output_format,
                                 light_mode=light_mode)
    except Exception as e:

        log.error("Unable to find {0}.".format(recid))
        log.error(e)
        return render_template('hepdata_theme/404.html')


@login_required
@blueprint.route('/<int:recid>/<int:version>/notify', methods=['POST'], strict_slashes=True)
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
    Queries and returns a data record
    :param recid: the record id being queried
    :return: renders the record template
    """
    version = int(request.args.get('version', -1))
    serialization_format = request.args.get('format', 'html')

    try:
        record = get_record_contents(recid)
    except Exception as e:
        record = None

    if record is None:
        return render_template('hepdata_theme/404.html')

    return render_record(recid=recid, record=record, version=version, output_format=serialization_format)


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


@blueprint.route('/data/<int:recid>/<int:data_recid>/<int:version>', methods=['GET', ])
def get_table_details(recid, data_recid, version):
    """

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

            try:
                table_contents = yaml.load(file(file_location), Loader=yaml.CSafeLoader)
            except:
                table_contents = yaml.load(file(file_location))

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
    hepsubmission_record = get_latest_hepsubmission(recid=recid)

    participants = {"reviewer": {"reserve": [], "primary": []},
                    "uploader": {"reserve": [], "primary": []}}

    for participant in hepsubmission_record.participants:
        participants[participant.role][participant.status].append(
            {"full_name": participant.full_name, "email": participant.email,
             "id": participant.id})

    print(participants)
    return json.dumps(
        {"recid": recid,
         "primary-reviewers": participants["reviewer"]["primary"],
         "reserve-reviewers": participants["reviewer"]["reserve"],
         "primary-uploaders": participants["uploader"]["primary"],
         "reserve-uploaders": participants["uploader"]["reserve"]})


@blueprint.route('/data/review/status/', methods=['POST', ])
@login_required
def set_data_review_status():
    # todo: need to check if the user is involved in this record before being allowed to perform this operation.
    # same for upload...

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


@blueprint.route('/resources/<int:recid>/<int:version>', methods=['GET'])
@returns_json
def get_resources(recid, version):
    """
    Gets a list of resources for a publication, relevant to all data records
    :param recid:
    :return: json
    """

    result = []
    submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version)

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
    return process_payload(id, file, '/record/sandbox/{}')


@login_required
@blueprint.route('/sandbox/<int:recid>/consume', methods=['POST'])
def update_sandbox_payload(recid):
    # generate a unique id

    file = request.files['hep_archive']
    return process_payload(recid, file, '/record/sandbox/{}')
