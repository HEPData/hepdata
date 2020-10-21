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

from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user

from hepdata.ext.elasticsearch.admin_view.api import AdminIndexer
from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.ext.elasticsearch.api import push_data_keywords
from hepdata.modules.dashboard.api import prepare_submissions, get_pending_invitations_for_user, get_submission_count, list_submission_titles
from hepdata.modules.permissions.api import get_pending_request, get_pending_coordinator_requests
from hepdata.modules.permissions.views import check_is_sandbox_record
from hepdata.modules.records.utils.submission import unload_submission, do_finalise
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.workflow import update_record
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.utils.url import modify_query
import json
import math

from invenio_userprofiles import current_userprofile

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
    """
    user_profile = current_userprofile.query.filter_by(user_id=current_user.get_id()).first()

    ctx = {'user_is_admin': has_role(current_user, 'admin'),
           'user_profile': user_profile,
           'user_has_coordinator_request': get_pending_request(),
           'pending_coordinator_requests': get_pending_coordinator_requests(),
           'pending_invites': get_pending_invitations_for_user(current_user)}

    return render_template('hepdata_dashboard/dashboard.html', ctx=ctx)


@blueprint.route('/dashboard-submissions')
@login_required
def dashboard_submissions():
    filter_record_id = request.args.get('record_id')
    current_page = request.args.get('page', default=1, type=int)
    size = request.args.get('size', 25)
    submissions = prepare_submissions(
        current_user,
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

    total_records = get_submission_count(current_user)
    total_pages = int(math.ceil(total_records / size))

    ctx = {
        'modify_query': modify_query,
        'submissions': submission_meta,
        'submission_stats': submission_stats
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
def dashboard_submission_titles():
    return jsonify(list_submission_titles(current_user))



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

        if submission.version == 1:
            admin_idx = AdminIndexer()
            admin_idx.find_and_delete('recid', recid)

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
    from flask import abort

    if has_role(current_user, 'admin'):
        user_profile = current_userprofile.query.filter_by(user_id=current_user.get_id()).first()

        ctx = {'user_is_admin': True,
               'user_profile': user_profile}
        return render_template('hepdata_dashboard/submissions.html', ctx=ctx)
    else:
        abort(403)


@blueprint.route('/submissions/list', methods=['GET'])
@login_required
def submissions_list():
    admin_idx = AdminIndexer()
    summary = admin_idx.get_summary()
    return jsonify(summary)
