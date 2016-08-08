from __future__ import absolute_import, print_function

from collections import OrderedDict
from flask import Blueprint, jsonify, request, render_template, redirect, \
    url_for
from flask.ext.login import login_required, current_user

from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.ext.elasticsearch.api import push_data_keywords
from hepdata.modules.records.api import get_user_from_id
from hepdata.modules.submission.models import HEPSubmission, DataReview, \
    SubmissionParticipant
from hepdata.modules.records.utils.common import get_record_by_id, encode_string
from hepdata.modules.records.utils.submission import unload_submission, get_latest_hepsubmission, do_finalise
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.submission.views import send_cookie_email
from invenio_accounts.models import User
from invenio_db import db
from invenio_userprofiles import UserProfile
import json
from operator import and_, or_

__author__ = 'eamonnmaguire'

blueprint = Blueprint('hep_dashboard', __name__, url_prefix="/dashboard",
                      template_folder='templates',
                      static_folder='static')


def add_user_to_metadata(type, user_info, record_id, submissions):
    if user_info:
        submissions[record_id]["metadata"][type] = {
            'name': user_info['full_name'],
            'email': user_info['email']}
    else:
        submissions[record_id]["metadata"][type] = {
            'name': 'No primary ' + type}


def create_record_for_dashboard(record_id, submissions, primary_uploader=None,
                                primary_reviewer=None, coordinator=None,
                                user_role=None,
                                status="todo"):
    if user_role is None:
        user_role = ["coordinator"]

    publication_record = get_record_by_id(int(record_id))

    if publication_record is not None:
        if record_id not in submissions:

            hepdata_submission_record = get_latest_hepsubmission(record_id)

            submissions[record_id] = {}
            submissions[record_id]["metadata"] = {"recid": record_id,
                                                  "role": user_role,
                                                  "start_date": publication_record.created}

            submissions[record_id]["metadata"][
                "versions"] = hepdata_submission_record.version
            submissions[record_id]["status"] = status
            submissions[record_id]["stats"] = {"passed": 0, "attention": 0,
                                               "todo": 0}

            if coordinator:
                submissions[record_id]["metadata"]["coordinator"] = {
                    'id': coordinator.id, 'name': coordinator.email,
                    'email': coordinator.email}
                submissions[record_id]["metadata"][
                    "show_coord_view"] = int(current_user.get_id()) == coordinator.id
            else:
                submissions[record_id]["metadata"]["coordinator"] = {
                    'name': 'No coordinator'}

            if "title" in publication_record:
                submissions[record_id]["metadata"]["title"] = \
                    publication_record['title']

            if "inspire_id" not in publication_record or publication_record["inspire_id"] is None:
                submissions[record_id]["metadata"][
                    "requires_inspire_id"] = True
        else:
            # if it is, it's because the user has two roles for that
            # submission. So we should show them!
            if user_role not in submissions[record_id]["metadata"]["role"]:
                submissions[record_id]["metadata"]["role"].append(user_role)


def process_user_record_results(type, query_results, submissions):
    """
    :param type: e.g. reviewer, uploader, or coordinator
    :param query_results: the records to be processed
    :param submissions: the submissions to be added to
    :return:
    """
    for submission in query_results:

        record_query_results = DataReview.query.filter_by(
            publication_recid=submission.publication_recid,
            version=submission.version).order_by(
            DataReview.id.asc()).all()

        if record_query_results:
            count = 0
            allow_record_count_updates = True

            for record in record_query_results:
                # this is a way to stop the counts for records being
                # updated two or three times for users with
                # multiple roles...
                if count == 0:
                    allow_record_count_updates = str(
                        record.publication_recid) not in submissions

                create_record_for_dashboard(str(record.publication_recid),
                                            submissions,
                                            user_role=[type])

                if allow_record_count_updates:
                    submissions[str(record.publication_recid)]["stats"][
                        record.status] += 1

                count += 1
        else:
            create_record_for_dashboard(str(submission.publication_recid),
                                        submissions, user_role=[type])


def prepare_submissions(current_user):
    """
    Finds all the relevant submissions for a user, or all submissions if the logged in user is a 'super admin'
    :param current_user: User obj
    :return: OrderedDict of submissions
    """

    submissions = OrderedDict()
    hepdata_submission_records = []

    if has_role(current_user, 'admin'):
        # if the user is a superadmin, show everything here.
        # The final rendering in the dashboard should be different
        # though considering the user him/herself is probably not a
        # reviewer/uploader
        hepdata_submission_records = HEPSubmission.query.filter(
            and_(HEPSubmission.overall_status != 'finished', HEPSubmission.overall_status != 'sandbox')).order_by(
            HEPSubmission.created.desc()).all()
    else:
        # we just want to pick out people with access to particular records,
        # i.e. submissions for which they are primary reviewers.

        participant_records = SubmissionParticipant.query.filter_by(
            user_account=int(current_user.get_id()),
            status='primary').all()

        for participant_record in participant_records:
            hepdata_submission_records = HEPSubmission.query.filter(
                HEPSubmission.publication_recid == participant_record.publication_recid,
                and_(HEPSubmission.overall_status != 'finished',
                     HEPSubmission.overall_status != 'sandbox')).all()

        coordinator_submissions = HEPSubmission.query.filter(
            HEPSubmission.coordinator == int(current_user.get_id()),
            and_(HEPSubmission.overall_status != 'finished',
                 HEPSubmission.overall_status != 'sandbox')).all()

        hepdata_submission_records += coordinator_submissions

    for hepdata_submission in hepdata_submission_records:

        if str(hepdata_submission.publication_recid) not in submissions:

            primary_uploader = primary_reviewer = None

            coordinator = User.query.get(hepdata_submission.coordinator)

            if hepdata_submission.participants:
                current_user_roles = []

                for participant in hepdata_submission.participants:

                    if int(current_user.get_id()) == participant.user_account:
                        current_user_roles.append(participant.role)

                    if participant.status == 'primary' and participant.role == "uploader":
                        primary_uploader = {'full_name': participant.full_name,
                                            'email': participant.email}
                    if participant.status == 'primary' and participant.role == "reviewer":
                        primary_reviewer = {'full_name': participant.full_name,
                                            'email': participant.email}

                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    primary_uploader=primary_uploader,
                    primary_reviewer=primary_reviewer,
                    coordinator=coordinator,
                    user_role=current_user_roles,
                    status=hepdata_submission.overall_status)
            else:
                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    coordinator=coordinator,
                    status=hepdata_submission.overall_status)

            # we update the counts for the number of data tables in various
            # states of review
            statuses = ["todo", "attention", "passed"]
            for status in statuses:
                status_count = DataReview.query.filter_by(
                    publication_recid=hepdata_submission.publication_recid,
                    status=status,
                    version=hepdata_submission.version).count()
                if str(hepdata_submission.publication_recid) in submissions:
                    submissions[str(hepdata_submission.publication_recid)][
                        "stats"][status] += status_count

    return submissions


def get_pending_invitations_for_user(user):
    pending_invites = SubmissionParticipant.query.filter(
        SubmissionParticipant.email == user.email,
        or_(SubmissionParticipant.role == 'reviewer',
            SubmissionParticipant.role == 'uploader'),
        SubmissionParticipant.user_account == None
    ).all()

    result = []

    for invite in pending_invites:
        publication_record = get_record_by_id(invite.publication_recid)
        hepsubmission = get_latest_hepsubmission(invite.publication_recid)

        coordinator = get_user_from_id(hepsubmission.coordinator)
        result.append(
            {'title': encode_string(publication_record['title'], 'utf-8'),
             'invitation_cookie': invite.invitation_cookie,
             'role': invite.role, 'coordinator': coordinator})

    return result


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
