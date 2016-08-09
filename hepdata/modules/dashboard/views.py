from __future__ import absolute_import, print_function

from flask import Blueprint, jsonify, request, render_template, redirect, \
    url_for
from flask.ext.login import login_required, current_user
from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.ext.elasticsearch.api import push_data_keywords
from hepdata.modules.dashboard.api import prepare_submissions, get_pending_invitations_for_user
from hepdata.modules.submission.models import HEPSubmission, SubmissionParticipant
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.submission import unload_submission, get_latest_hepsubmission, do_finalise
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.submission.views import send_cookie_email
from invenio_db import db
from invenio_userprofiles import UserProfile
import json

__author__ = 'eamonnmaguire'

blueprint = Blueprint('hep_dashboard', __name__, url_prefix="/dashboard",
                      template_folder='templates',
                      static_folder='static')


@blueprint.route('/')
@login_required
def dashboard():
    """
        Depending on the user that is logged in, they will get a
        dashboard that reflects the
        current status of all submissions of which they are part.
    """

    submissions = prepare_submissions(current_user)

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

    user_profile = UserProfile.query.filter_by(user_id=current_user.get_id()).first()

    ctx = {'user_is_admin': has_role(current_user, 'admin'),
           'submissions': submission_meta,
           'user_profile': user_profile,
           'submission_stats': json.dumps(submission_stats),
           'pending_invites': get_pending_invitations_for_user(current_user)}

    return render_template('hepdata_dashboard/dashboard.html', ctx=ctx)


@blueprint.route(
    '/manage/<int:recid>/<string:action>/<string:demote_or_promote>/<int:participant_id>')
@login_required
def promote_or_demote_participant(recid, action, demote_or_promote,
                                  participant_id):
    """
    Can promote or demote a participant to/from primary reviewer/uploader
    :param recid: record id that the user will be promoted or demoted
    :param action: upload or review
    :param demote_or_promote: demote or promote
    :param participant_id: id of user from the SubmissionParticipant table.
    :return:
    """
    try:
        participant = SubmissionParticipant.query.filter_by(
            id=participant_id).one()

        status = 'reserve'
        if demote_or_promote == 'promote':
            status = 'primary'

        participant.status = status
        db.session.add(participant)
        db.session.commit()

        record = get_record_by_id(recid)

        # now send the email telling the user of their new status!
        if status == 'primary':
            send_cookie_email(participant, record)

        return json.dumps({"success": True, "recid": recid})
    except Exception as e:
        return json.dumps(
            {"success": False, "recid": recid, "error": e.message})


@blueprint.route('/manage/person/add/<int:recid>', methods=['POST'])
@login_required
def add_participant(recid):
    """
    Adds a participant to a record
    :param recid:
    :return:
    """
    try:
        submission_record = get_latest_hepsubmission(recid)
        full_name = request.form['name']
        email = request.form['email']
        participant_type = request.form['type']

        new_record = SubmissionParticipant(publication_recid=recid,
                                           full_name=full_name,
                                           email=email, role=participant_type)
        submission_record.participants.append(new_record)
        db.session.commit()
        return json.dumps(
            {"success": True, "recid": recid,
             "message": "{0} {1} added.".format(full_name, participant_type)})

    except Exception as e:
        print(e)
        return json.dumps(
            {"success": False, "recid": recid,
             "message": 'Unable to add participant.'})


@blueprint.route('/manage/coordinator/', methods=['POST'])
@login_required
def change_coordinator_for_submission():
    """
    Changes the coordinator for a record to that defined by a coordinate.
    Accepts a data object containing {'recid': record id to be acted upon,
    'coordinator': id of user who will now be the coordinator}
    :return: dict
    """

    recid = request.form['recid']
    coordinator_id = request.form['coordinator']
    submission_record = HEPSubmission.query.filter_by(
        publication_recid=recid).one()

    submission_record.coordinator = coordinator_id
    db.session.add(submission_record)
    db.session.commit()

    return jsonify({'success': True})


@blueprint.route('/assign/<cookie>')
@login_required
def assign_role(cookie):
    participant_record = SubmissionParticipant.query.filter_by(
        invitation_cookie=cookie).first()
    participant_record.user_account = current_user.get_id()

    db.session.add(participant_record)
    db.session.commit()

    return redirect(url_for('.dashboard'))


def check_is_sandbox_record(recid):
    try:
        submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
        print(submission.overall_status)
        return submission.overall_status == 'sandbox'
    except Exception as e:
        print(e)
        return False


@blueprint.route('/delete/<int:recid>')
@login_required
def delete_submission(recid):
    """
    Submissions can only be removed if they are not finalised,
    meaning they should never be in the index.
    :param recid:
    :return:
    """
    print('Is sandbox {0} == {1} '.format(recid, check_is_sandbox_record(recid)))
    if has_role(current_user, 'admin') or has_role(current_user, 'coordinator') \
        or check_is_sandbox_record(recid):
        unload_submission(recid)
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
        # we reindex all
        reindex_all(recreate=True)
        push_data_keywords()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False,
                        'message': "You don't have sufficient privileges to "
                                   "perform this action."})


@blueprint.route('/finalise/<int:recid>', methods=['POST'])
@login_required
def finalise(recid, publication_record=None, force_finalise=False):
    commit_message = request.form.get('message')

    return do_finalise(recid, publication_record, force_finalise,
                       commit_message=commit_message, send_tweet=True)
