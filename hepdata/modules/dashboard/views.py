from __future__ import absolute_import, print_function
from collections import OrderedDict
from datetime import datetime
import json
from operator import or_, and_

from flask.ext.celeryext import create_celery_app
from flask.ext.login import login_required, current_user
from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy.orm.exc import NoResultFound
from hepdata.config import CFG_DATA_TYPE
from hepdata.ext.elasticsearch.api import reindex_all, \
    get_records_matching_field, delete_item_from_index, index_record_ids
from hepdata.ext.elasticsearch.api import push_data_keywords
from hepdata.modules.records.models import HEPSubmission, DataReview, \
    SubmissionParticipant, DataSubmission, RecordVersionCommitMessage
from hepdata.modules.records.utils.common import get_record_by_id
from flask import Blueprint, jsonify, request, render_template, redirect, \
    url_for, current_app

from hepdata.modules.records.utils.doi_minter import register_doi, generate_doi_for_data_submission, \
    generate_doi_for_submission
from hepdata.modules.records.utils.submission import unload_submission, package_submission
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.records.utils.workflow import send_finalised_email, \
    create_record
from hepdata.utils.twitter import tweet

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

            hepdata_submission_record = HEPSubmission.query.filter_by(
                publication_recid=record_id).first()

            submissions[record_id] = {}
            submissions[record_id]["metadata"] = {"recid": record_id,
                                                  "role": user_role,
                                                  "start_date": publication_record.created}

            submissions[record_id]["metadata"][
                "versions"] = hepdata_submission_record.latest_version
            submissions[record_id]["status"] = status
            submissions[record_id]["stats"] = {"passed": 0, "attention": 0,
                                               "todo": 0}

            add_user_to_metadata("uploader", primary_uploader, record_id,
                                 submissions)
            add_user_to_metadata("reviewer", primary_reviewer, record_id,
                                 submissions)

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
            else:
                submissions[record_id]["metadata"][
                    "title"] = "Submission in Progress"

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
            version=submission.latest_version).order_by(
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
    :param invenio_user: current user
    :return:
    """

    submissions = OrderedDict()
    hepdata_submission_records = []

    if has_role(current_user, 'admin'):
        # if the user is a superadmin, show everything here.
        # The final rendering in the dashboard should be different
        # though considering the user him/herself is probably not a
        # reviewer/uploader
        hepdata_submission_records = HEPSubmission.query.filter(
            or_(HEPSubmission.overall_status == 'todo',
                or_(HEPSubmission.overall_status == 'attention',
                    HEPSubmission.overall_status == 'passed'),
                )).order_by(
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
            HEPSubmission.coordinator == int(current_user.get_id())).all()
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
                    version=hepdata_submission.latest_version).count()
                if str(hepdata_submission.publication_recid) in submissions:
                    submissions[str(hepdata_submission.publication_recid)][
                        "stats"][status] += status_count

    return submissions


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

        review_status = "Not started"
        review_flag = "todo"
        if submissions[record_id]["stats"]["attention"] == 0 and \
                submissions[record_id]["stats"]["todo"] == 0 and \
                submissions[record_id]["stats"]["passed"] == 0:
            review_status = "Not started"
            review_flag = "todo"
        elif submissions[record_id]["stats"]["attention"] > 0 or \
                submissions[record_id]["stats"]["todo"] > 0:
            review_status = "In progress"
            review_flag = "attention"
        elif submissions[record_id]["stats"]["attention"] == 0 and \
                submissions[record_id]["stats"]["todo"] == 0:
            review_status = "Awaiting Action"
            review_flag = "passed"

        if submissions[record_id]["status"] == 'finished':
            review_status = "Finished"
            review_flag = "finished"

        submissions[record_id]["metadata"]["submission_status"] = \
            submissions[record_id]["status"]
        submissions[record_id]["metadata"]["review_status"] = review_status
        submissions[record_id]["metadata"]["review_flag"] = review_flag

        submission_meta.append(submissions[record_id]["metadata"])

    ctx = {'user_is_admin': has_role(current_user, 'admin'),
           "submissions": submission_meta,
           "submission_stats": json.dumps(submission_stats)}

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
        # if status == 'primary':
        # send_cookie_email(recid, record['title']['title'], action,
        #                   {'email': participant.email,
        #                    'full_name': participant.full_name})

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
        submission_record = HEPSubmission.query.filter_by(
            publication_recid=recid).one()
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


@blueprint.route('/delete/<int:recid>')
@login_required
def delete_submission(recid):
    """
    Submissions can only be removed if they are not finalised,
    meaning they should never be in the index.
    :param recid:
    :return:
    """
    if has_role(current_user, 'admin') or has_role(current_user, 'coordinator'):
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


def do_finalise(recid, publication_record=None, force_finalise=False,
                commit_message=None, send_tweet=False):
    """
        Creates record SIP for each data record with a link to the associated
        publication
        and submits to bibupload.
        :param synchronous: if true then workflow execution and creation is
        waited on, then everything is indexed in one go.
        If False, object creation is asynchronous, however reindexing is not
        performed. This is only really useful for the full migration of
        content.
    """
    hep_submission = HEPSubmission.query.filter_by(
        publication_recid=recid).first()

    print('Finalising record {}'.format(recid))

    generated_record_ids = []
    # check if current user is the coordinator
    if force_finalise or hep_submission.coordinator == int(current_user.get_id()):

        submissions = DataSubmission.query.filter_by(
            publication_recid=recid,
            version=hep_submission.latest_version).all()

        # this only happens for the first upload where the version is set to 0.
        if hep_submission.latest_version == 0:
            version = hep_submission.latest_version + 1
        else:
            version = hep_submission.latest_version

        existing_submissions = {}
        if hep_submission.latest_version > 0:
            # we need to determine which are the existing record ids.
            existing_data_records = get_records_matching_field(
                'related_publication', recid, doc_type=CFG_DATA_TYPE)

            for record in existing_data_records["hits"]["hits"]:

                if "recid" in record["_source"]:
                    existing_submissions[record["_source"]["title"]] = \
                        record["_source"]["recid"]
                    delete_item_from_index(record["_id"],
                                           doc_type=CFG_DATA_TYPE)

        current_time = "{:%Y-%m-%d}".format(datetime.now())

        for submission in submissions:
            finalise_datasubmission(current_time, existing_submissions,
                                    generated_record_ids,
                                    publication_record, recid, submission,
                                    version)

        try:
            record = get_record_by_id(recid)
            # If we have a commit message, then we have a record update.
            # We will store the commit message and also update the
            # last_updated flag for the record.
            record['hepdata_doi'] = hep_submission.doi

            if commit_message:
                record['last_updated'] = current_time

                commit_record = RecordVersionCommitMessage(
                    recid=recid,
                    version=version,
                    message=commit_message)

                db.session.add(commit_record)
            else:
                record['last_updated'] = datetime.strftime(hep_submission.last_updated, '%d/%m/%y %H:%M:%S')

            record.commit()

            hep_submission.overall_status = "finished"
            hep_submission.latest_version = version
            db.session.add(hep_submission)

            db.session.commit()

            create_celery_app(current_app)

            for submission in submissions:
                generate_doi_for_data_submission.delay(submission.id, submission.version)

            generate_doi_for_submission.delay(recid, version)

            # Reindex everything.
            index_record_ids([recid] + generated_record_ids)
            push_data_keywords(pub_ids=[recid])

            send_finalised_email(hep_submission)

            if send_tweet:
                tweet(record.get('title'), record.get('collaborations'),
                      "http://www.hepdata.net/record/ins{0}".format(record.get('inspire_id')))

            return json.dumps({"success": True, "recid": recid,
                               "data_count": len(submissions),
                               "generated_records": generated_record_ids})

        except NoResultFound:
            print('No record found to update. Which is super strange.')

    else:
        return json.dumps(
            {"success": False, "recid": recid,
             "errors": ["You do not have permission to finalise this "
                        "submission. Only coordinators can do that."]})


def finalise_datasubmission(current_time, existing_submissions,
                            generated_record_ids, publication_record, recid,
                            submission, version):
    # we now create a 'payload' for each data submission
    # by creating a record json and uploading it via a bibupload task.
    # add in key for associated publication...
    keywords = []
    for keyword in submission.keywords:
        keywords.append({"name": keyword.name,
                         "value": keyword.value,
                         "synonyms": ""})

    # we want to retrieve back the authors of the paper
    # and assign them as authors of the data too
    if not publication_record:
        publication_record = get_record_by_id(recid)

    submission_info = {
        "title": submission.name,
        "abstract": submission.description,
        "inspire_id": publication_record['inspire_id'],
        "doi": submission.doi,
        "authors": publication_record['authors'],
        "first_author": publication_record['first_author'],
        "related_publication": submission.publication_recid,
        "creation_date": publication_record["creation_date"],
        "last_updated": current_time,
        "journal_info": publication_record.get("journal_info", ""),
        "keywords": keywords,
        "version": version,
        "collaborations": publication_record.get("collaborations", []),
    }

    if submission_info["title"] in existing_submissions:
        # in the event that we're performing an update operation, we need
        # to get the data record information
        # from the index, and use the same record id. This way, we'll just
        # update the submission instead of recreating
        # a completely new record.
        recid = existing_submissions[submission_info["title"]]
        submission_info["control_number"] = submission_info["recid"] = recid

    else:
        submission_info = create_record(submission_info)
        submission_info["control_number"] = submission_info["recid"]

    submission.associated_recid = submission_info['recid']
    generated_record_ids.append(submission_info["recid"])
    submission_info["data_endpoints"] = create_data_endpoints(submission.id,
                                                              submission_info)

    submission.version = version

    data_review = DataReview.query.filter_by(data_recid=submission.id).first()
    if data_review:
        data_review.version = version
        db.session.add(data_review)

    db.session.add(submission)


def create_data_endpoints(data_id, info_dict):
    """ Generate dictionary describing endpoints
    where different data formats are served"""

    from hepdata.config import CFG_DATA_TYPE

    parent_param = "?parent=" + str(info_dict["related_publication"])
    return {
        "json": "/".join(["/api",
                          "record",
                          CFG_DATA_TYPE,
                          str(info_dict["recid"]),
                          "json" + parent_param]),
        "csv": "/".join(["",
                         "record",
                         CFG_DATA_TYPE,
                         "file",
                         str(data_id),
                         "csv"])
    }
