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

"""HEPData Dashboard Views."""

from flask import Blueprint, jsonify, request, render_template, abort, \
    current_app, make_response, url_for
from flask_login import login_required, current_user
from invenio_accounts.models import User, Role

from hepdata.ext.opensearch.admin_view.api import AdminIndexer
from hepdata.ext.opensearch.api import reindex_all
from hepdata.ext.opensearch.api import push_data_keywords
from hepdata.modules.dashboard.api import prepare_submissions, get_pending_invitations_for_user, get_submission_count, \
    list_submission_titles, get_dashboard_current_user, set_dashboard_current_user, get_submissions_summary, \
    get_submissions_csv
from hepdata.modules.permissions.api import get_pending_request, get_pending_coordinator_requests
from hepdata.modules.permissions.views import check_is_sandbox_record
from hepdata.modules.records.utils.submission import unload_submission, do_finalise
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.ext import user_is_admin_or_coordinator
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.workflow import update_record
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.utils.url import modify_query
import collections
import json
import math

from invenio_userprofiles import current_userprofile, UserProfile

blueprint = Blueprint('hep_dashboard', __name__, url_prefix="/dashboard",
                      template_folder='templates',
                      static_folder='static')


@blueprint.route('/')
@login_required
def dashboard():
    """
    Depending on the user that is logged in, they will get a
    dashboard that reflects the
    current status of all submissions of which they are a participant.

    An admin user can view the dashboard as if they were a different user,
    using the view_as parameter
    """
    view_as_user_id = request.args.get('view_as_user', type=int)
    if view_as_user_id:
        try:
            user_to_display = set_dashboard_current_user(current_user, view_as_user_id)
        except ValueError:
            abort(404)
    else:
        user_to_display = get_dashboard_current_user(current_user)

    if user_to_display == current_user:
        user_profile = current_userprofile.query.filter_by(user_id=user_to_display.get_id()).first()
    else:
        user_profile = UserProfile.query.filter_by(user_id=user_to_display.get_id()).first()


    ctx = {'user_is_admin': has_role(user_to_display, 'admin'),
           'user_profile': user_profile,
           'user_to_display': user_to_display,
           'view_as_mode': user_to_display != current_user,
           'user_is_coordinator_or_admin': user_is_admin_or_coordinator(user_to_display),
           'user_has_coordinator_request': get_pending_request(),
           'pending_coordinator_requests': get_pending_coordinator_requests(),
           'pending_invites': get_pending_invitations_for_user(user_to_display)}

    return render_template('hepdata_dashboard/dashboard.html', ctx=ctx)


@blueprint.route('/dashboard-submissions')
@login_required
def dashboard_submissions():
    user = get_dashboard_current_user(current_user)
    view_as_mode = user != current_user

    filter_record_id = request.args.get('record_id')
    current_page = request.args.get('page', default=1, type=int)
    size = request.args.get('size', 25)
    submissions = prepare_submissions(
        user,
        items_per_page=size,
        current_page=current_page,
        record_id=filter_record_id
    )

    submission_meta = []
    submission_stats = []

    for record_id in submissions:
        stats = []

        for key in submissions[record_id]["stats"].keys():
            stats.append(
                {"name": key, "count": submissions[record_id]["stats"][key]})

        submission_stats.append({"recid": record_id, "stats": stats})

        review_flag = "todo"
        if submissions[record_id]["stats"]["attention"] == 0 and \
                submissions[record_id]["stats"]["todo"] == 0 and \
                submissions[record_id]["stats"]["passed"] == 0:
            review_flag = "todo"
        elif submissions[record_id]["stats"]["attention"] > 0 or \
                submissions[record_id]["stats"]["todo"] > 0:
            review_flag = "attention"
        elif submissions[record_id]["stats"]["attention"] == 0 and \
                submissions[record_id]["stats"]["todo"] == 0:
            review_flag = "passed"

        if submissions[record_id]["status"] == 'finished':
            review_flag = "finished"

        submissions[record_id]["metadata"]["submission_status"] = \
            submissions[record_id]["status"]
        submissions[record_id]["metadata"]["review_flag"] = review_flag

        submission_meta.append(submissions[record_id]["metadata"])

    total_records = get_submission_count(user)
    total_pages = int(math.ceil(total_records / size))

    ctx = {
        'user_is_admin': has_role(user, 'admin'),
        'view_as_mode': view_as_mode,
        'modify_query': modify_query,
        'submissions': submission_meta,
        'submission_stats': json.dumps(submission_stats)
    }

    if filter_record_id is None:
        ctx['pages'] = {
            'total': total_pages,
            'current': current_page,
            'endpoint': '.dashboard'
        }

    return render_template('hepdata_dashboard/dashboard-submissions.html', ctx=ctx)


@blueprint.route('/dashboard-submission-titles')
@login_required
def dashboard_submission_titles(user=current_user):
    if user != current_user and not has_role(current_user, 'admin'):
        abort(403)

    return jsonify(list_submission_titles(user))


@blueprint.route('/delete/<int:recid>')
@login_required
def delete_submission(recid):
    """
    Submissions can only be removed if they are not finalised,
    meaning they should never be in the index.
    Only delete the latest version of a submission.
    Delete indexed information only if version = 1.

    :param recid:
    :return:
    """
    if has_role(current_user, 'admin') or has_role(current_user, 'coordinator') \
        or check_is_sandbox_record(recid):

        submission = get_latest_hepsubmission(publication_recid=recid)
        unload_submission(recid, submission.version)

        admin_idx = AdminIndexer()
        admin_idx.delete_by_id(submission.id)

        return json.dumps({"success": True,
                           "recid": recid,
                           "errors": [
                               "Record successfully removed!"]})
    else:
        return json.dumps(
            {"success": False, "recid": recid,
             "errors": [
                 "You do not have permission to delete this submission. "
                 "Only coordinators can do that."]})


@blueprint.route('/manage/reindex/', methods=['POST'])
@login_required
def reindex():
    if has_role(current_user, 'admin'):
        reindex_all(recreate=True)
        push_data_keywords()
        admin_idx = AdminIndexer()
        admin_idx.reindex(recreate=True)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False,
                        'message': "You don't have sufficient privileges to "
                                   "perform this action."})


@blueprint.route('/finalise/<int:recid>', methods=['POST'])
@login_required
def finalise(recid, publication_record=None, force_finalise=False):
    commit_message = request.form.get('message')

    # Update publication information from INSPIRE record before finalising.
    if not publication_record:
        record = get_record_by_id(recid)
        content, status = get_inspire_record_information(record['inspire_id'])
        if status == 'success':
            publication_record = update_record(recid, content)

    return do_finalise(recid, publication_record=publication_record, force_finalise=force_finalise,
                       commit_message=commit_message, send_tweet=True)


@blueprint.route('/submissions/', methods=['GET'])
@login_required
def submissions():
    view_as_user_id = request.args.get('view_as_user', type=int)
    if view_as_user_id:
        try:
            user = set_dashboard_current_user(current_user, view_as_user_id)
        except ValueError:
            abort(404)
    else:
        user = get_dashboard_current_user(current_user)

    if has_role(user, 'admin') or has_role(user, 'coordinator'):
        user_profile = UserProfile.query.filter_by(user_id=user.get_id()).first()
        url_for_params = { 'view_as_user': user.id } if user != current_user else {}
        dashboard_url = url_for('hep_dashboard.dashboard', **url_for_params)

        ctx = {'user_is_admin': has_role(user, 'admin'),
               'user_is_coordinator_or_admin': user_is_admin_or_coordinator(user),
               'user_profile': user_profile,
               'user_to_display': user,
               'view_as_mode': user != current_user,
               'dashboard_url': dashboard_url }
        return render_template('hepdata_dashboard/submissions.html', ctx=ctx)
    else:
        abort(403)


@blueprint.route('/submissions/list', methods=['GET'])
@login_required
def submissions_list():
    user = get_dashboard_current_user(current_user)
    if not (has_role(user, 'admin') or has_role(user, 'coordinator')):
        return {"success": False,
                'message': "You don't have sufficient privileges to "
                           "perform this action."}

    summary = get_submissions_summary(
        user,
        include_imported=current_app.config.get('TESTING', False)
    )

    return jsonify(summary)


@blueprint.route('/submissions/csv', methods=['GET'])
@login_required
def submissions_csv():
    user = get_dashboard_current_user(current_user)
    if not (has_role(user, 'admin') or has_role(user, 'coordinator')):
        abort(403)

    csv_data = get_submissions_csv(
        user,
        include_imported=current_app.config.get('TESTING', False)
    )
    output = make_response(csv_data)
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@blueprint.route('/list-all-users')
@login_required
def get_all_users():
    """
    Gets a list of all active users in the system.

    :return:
    """
    if has_role(current_user, 'admin'):
        coordinators_only = request.args.get(
            'coordinators_only', default=False,
            type=lambda v: v.lower() == 'true'
        )
        users_query = User.query.with_entities(User.id, User.email) \
            .filter_by(active=True)

        if coordinators_only:
            users_query = users_query.filter(User.roles.any(Role.name == 'coordinator'))

        users = users_query.all()
        return jsonify([{'id': u[0], 'email': u[1]} for u in users])
    else:
        abort(403)
