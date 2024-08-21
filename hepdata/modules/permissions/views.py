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


from datetime import datetime
import json
import logging

from flask_login import login_required, current_user
from invenio_accounts.models import Role
from invenio_db import db
from sqlalchemy import func

from flask import Blueprint, jsonify, url_for, redirect, request, abort, render_template

from hepdata.ext.opensearch.admin_view.api import AdminIndexer
from hepdata.modules.dashboard.api import get_dashboard_current_user
from hepdata.modules.email.api import send_coordinator_request_mail, send_coordinator_approved_email, \
    send_cookie_email, send_reserve_email
from hepdata.modules.permissions.api import get_records_participated_in_by_user, get_approved_coordinators, \
    get_pending_request
from hepdata.modules.permissions.models import SubmissionParticipant, CoordinatorRequest
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission
from hepdata.utils.users import get_user_from_id, user_is_admin

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint('hep_permissions', __name__, url_prefix="/permissions",
                      template_folder='templates')


@blueprint.route(
    '/manage/<int:recid>/<string:action>/<string:status_action>/<int:participant_id>', methods=['POST', 'GET'])
@login_required
def manage_participant_status(recid, action, status_action, participant_id):
    """
    Handles actions received from the "Manage Submission" widget window buttons.
    Manages user promotion/demotion for uploader and reviewer roles,
    removal of reserve users, and email reminders to primary uploaders/reviewers
    Request can contain a message for reminder email.

    status_action possibilities are:
        promote: Promote a reserve uploader/reviewer to primary position
        demote: Demote a reserve uploader/reviewer from primary position
        email: Send reminder email to primary uploader/reviewer
        remove: Remove a reserve uploader/reviewer from the submission

    :param recid: ID of target record to manage
    :param action: (Unused) Target of the action ('upload', OR 'review')
    :param status_action: The status of which action button was clicked.
    :param participant_id: ID of target participant to update
    :return:
    """
    try:
        participant = SubmissionParticipant.query.filter_by(
            id=participant_id).one()

        if status_action != 'email':
            if status_action == 'remove':
                db.session.delete(participant)
            else:
                status = 'reserve'
                if status_action == 'promote':
                    status = 'primary'

                participant.status = status
                db.session.add(participant)

            db.session.commit()

        record = get_record_by_id(recid)

        # now send the email telling the user of their new status!
        hepsubmission = get_latest_hepsubmission(publication_recid=recid)
        if status_action != 'email':
            if status_action == 'promote':
                send_cookie_email(participant, record, version=hepsubmission.version)
            elif status_action == 'demote':
                send_reserve_email(participant, record)
            admin_idx = AdminIndexer()
            admin_idx.index_submission(hepsubmission)
        else:
            send_cookie_email(participant, record, version=hepsubmission.version, message=request.form['review_message'])



        return json.dumps({"success": True, "recid": recid})
    except Exception as e:
        error_str = f"Unable to {status_action} participant id {participant_id} for record {recid}"
        log.error(f"{error_str}: {str(e)}")
        return json.dumps(
            {"success": False, "recid": recid, "message": f"{error_str}. Please refresh the page and try again."})


@blueprint.route('/manage/person/add/<int:recid>', methods=['POST'])
@login_required
def add_participant(recid):
    """
    Adds a participant to a record.

    :param recid:
    :return:
    """
    try:
        submission_record = get_latest_hepsubmission(publication_recid=recid)
        full_name = request.form['name']
        email = request.form['email']
        participant_type = request.form['type']

        new_record = SubmissionParticipant(publication_recid=recid,
                                           full_name=full_name,
                                           email=email, role=participant_type)
        db.session.add(new_record)
        db.session.commit()

        admin_idx = AdminIndexer()
        admin_idx.index_submission(submission_record)

        return json.dumps(
            {"success": True, "recid": recid,
             "message": "{0} {1} added.".format(full_name, participant_type)})

    except Exception as e:
        return json.dumps(
            {"success": False, "recid": recid,
             "message": 'Unable to add participant.'})


@blueprint.route('/manage/coordinator/', methods=['POST'])
@login_required
def change_coordinator_for_submission():
    """
    Changes the coordinator for a record to that defined by a user id.
    Accepts a data object containing {'recid': record id to be acted upon,
    'coordinator': id of user who will now be the coordinator}.

    :return: dict
    """

    recid = request.form['recid']
    coordinator_id = request.form['coordinator']
    submission_records = HEPSubmission.query.filter_by(publication_recid=recid).all()
    admin_idx = AdminIndexer()
    for submission_record in submission_records:
        submission_record.coordinator = coordinator_id
        db.session.add(submission_record)
        admin_idx.index_submission(submission_record)
    db.session.commit()

    return jsonify({'success': True})


@blueprint.route('/request/coordinator/', methods=['POST'])
@login_required
def request_coordinator_privileges():
    """
    Submits a request for coordinator privileges.

    :return:
    """
    _user_id = int(current_user.get_id())
    message = request.form['message']
    experiment = request.form['experiment']

    existing_requests = get_pending_request()

    if len(existing_requests) > 0:
        return jsonify({'message': 'Pending coordinator requests already exist for this user.',
                        'status': 'error'})
    try:
        coordinator_request = CoordinatorRequest(user=_user_id, message=str(message), collaboration=experiment)

        db.session.add(coordinator_request)
        db.session.commit()

        send_coordinator_request_mail(coordinator_request)
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": e.__str__()})

    return jsonify({'message': 'Request sent successfully.', 'status': 'ok'})


@blueprint.route('/coordinator/response/<int:request_id>/<string:decision>', methods=['POST', 'GET'])
@login_required
def respond_coordinator_privileges(request_id, decision):
    """
    Handles a request for coordinator privileges.

    :return:
    """

    if user_is_admin(current_user):

        coordinator_request = CoordinatorRequest.query.filter_by(
            id=request_id).one()

        if coordinator_request:
            coordinator_request.in_queue = False
            if decision == 'approve':
                coordinator_request.approved = True

                coordinator_role = Role.query.filter_by(name='coordinator').one()
                if coordinator_role:

                    user = get_user_from_id(coordinator_request.user)
                    if user:
                        user.roles.append(coordinator_role)
                        db.session.add(user)
                        send_coordinator_approved_email(coordinator_request)
                    else:
                        return render_template('hepdata_records/error_page.html',
                                               recid=None,
                                               message="Unable to find a user with id {0} in the system.".format(
                                                   coordinator_request.user),
                                               errors={})

                else:
                    return render_template('hepdata_records/error_page.html', recid=None,
                                           message="Unable to find the role coordinator in the system.",
                                           errors={})

            db.session.add(coordinator_request)
            db.session.commit()

            return redirect(url_for('hep_dashboard.dashboard'))

        return render_template('hepdata_records/error_page.html', recid=None,
                               message="No request found with that ID.",
                               errors={})

    abort(403)


@blueprint.route('/assign/<cookie>')
@login_required
def assign_role(cookie):
    try:
        participant_record = SubmissionParticipant.query.filter(
            func.lower(SubmissionParticipant.email) == func.lower(current_user.email),
            SubmissionParticipant.invitation_cookie == cookie).first()
        participant_record.user_account = current_user.get_id()
        participant_record.action_date = datetime.utcnow()

        db.session.add(participant_record)
        db.session.commit()

        return redirect('/record/{0}'.format(participant_record.publication_recid))

    except:
        abort(403)


def check_is_sandbox_record(recid):
    try:
        submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
        return submission.overall_status.startswith('sandbox')
    except Exception as e:
        return False


@blueprint.route('/list')
@login_required
def get_permissions_list():
    """
    Gets all permissions given for a user.

    :return:
    """
    user = get_dashboard_current_user(current_user)
    return jsonify(get_records_participated_in_by_user(user))


@blueprint.route('/coordinators')
def get_coordinators():
    """
    Returns a list of coordinators and their experiments in the system.

    :return:
    """
    coordinators = get_approved_coordinators()
    return render_template('hepdata_permissions/coordinator_list.html',
                           coordinators=coordinators)
