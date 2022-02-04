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

"""HEPData Dashboard API."""

from collections import OrderedDict
import csv
import io

from flask import url_for
from invenio_accounts.models import User

from sqlalchemy import or_, func
from werkzeug.exceptions import Forbidden as ForbiddenError

from hepdata.ext.elasticsearch.admin_view.api import AdminIndexer
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.common import get_record_by_id, decode_string
from hepdata.modules.submission.api import get_latest_hepsubmission, get_submission_participants_for_record
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.submission.models import HEPSubmission, DataReview
from hepdata.utils.session import get_session_item, set_session_item
from hepdata.utils.users import get_user_from_id


VIEW_AS_USER_ID_KEY = 'dashboard_view_as_user_id'


def add_user_to_metadata(type, user_info, record_id, submissions):
    if user_info:
        submissions[record_id]["metadata"][type] = {
            'name': user_info['full_name'],
            'email': user_info['email']}
    else:
        submissions[record_id]["metadata"][type] = {
            'name': 'No primary ' + type}


def create_record_for_dashboard(record_id, submissions, user, coordinator=None, user_role=None,
                                status="todo"):
    if user_role is None:
        user_role = []

    publication_record = get_record_by_id(int(record_id))

    if publication_record is not None:
        if record_id not in submissions:

            hepdata_submission_record = get_latest_hepsubmission(publication_recid=record_id)

            submissions[record_id] = {}
            submissions[record_id]["metadata"] = {"recid": record_id,
                                                  "role": user_role,
                                                  "start_date": hepdata_submission_record.created,
                                                  "last_updated": hepdata_submission_record.last_updated}

            submissions[record_id]["metadata"][
                "versions"] = hepdata_submission_record.version
            submissions[record_id]["status"] = status
            submissions[record_id]["stats"] = {"passed": 0, "attention": 0,
                                               "todo": 0}

            if coordinator:
                submissions[record_id]["metadata"]["coordinator"] = {
                    'id': coordinator.id, 'name': coordinator.email,
                    'email': coordinator.email}
                if int(user.get_id()) == coordinator.id:
                    submissions[record_id]["metadata"]["show_coord_view"] = True
                    if 'coordinator' not in submissions[record_id]["metadata"]["role"]:
                        submissions[record_id]["metadata"]["role"].append("coordinator")
                else:
                    submissions[record_id]["metadata"]["show_coord_view"] = False
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


def get_submission_count(user):
    query = _prepare_submission_query(user)
    return query.count()


def prepare_submissions(user, items_per_page=25, current_page=1, record_id=None):
    """
    Finds all the relevant submissions for a user, or all submissions if the logged in user is a 'super admin'.

    :param current_user: User obj
    :param items_per_page: maximum number of items to return
    :param current_page: page of current set of results (starting at 1)
    :return: OrderedDict of submissions
    """
    submissions = OrderedDict()

    query = _prepare_submission_query(user)

    if record_id:
        query = query.filter(HEPSubmission.publication_recid == record_id)

    offset = (current_page - 1) * items_per_page

    hepdata_submission_records = query.order_by(
        HEPSubmission.last_updated.desc()
    ).limit(items_per_page).offset(offset).all()

    for hepdata_submission in hepdata_submission_records:

        if str(hepdata_submission.publication_recid) not in submissions:

            coordinator = User.query.get(hepdata_submission.coordinator)

            participants = get_submission_participants_for_record(
                hepdata_submission.publication_recid,
                user_account=user.id
            )

            if participants:
                user_roles = []

                for participant in participants:
                    user_roles.append(participant.role)

                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    user,
                    coordinator=coordinator,
                    user_role=user_roles,
                    status=hepdata_submission.overall_status)
            else:
                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    user,
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


def list_submission_titles(current_user):
    user = get_dashboard_current_user(current_user)
    query = _prepare_submission_query(user)

    hepdata_submission_records = query.order_by(
        HEPSubmission.last_updated.desc()
    ).all()

    titles = []
    for hepsubmission in hepdata_submission_records:
        publication_record = get_record_by_id(int(hepsubmission.publication_recid))
        if publication_record:
            titles.append({
                'id': int(hepsubmission.publication_recid),
                'title': publication_record['title']
            })

    return titles


def _prepare_submission_query(user):
    query = HEPSubmission.query.filter(
        HEPSubmission.overall_status.in_(['processing', 'todo']),
    )

    # if the user is a superadmin, show everything here.
    # The final rendering in the dashboard should be different
    # though considering the user him/herself is probably not a
    # reviewer/uploader
    if not has_role(user, 'admin'):
        # Not an admin user
        # We just want to pick out people with access to particular records,
        # i.e. submissions for which they are primary reviewers or coordinators.

        inner_query = SubmissionParticipant.query.filter_by(
            user_account=int(user.get_id()),
            status='primary'
        ).with_entities(
            SubmissionParticipant.publication_recid
        )

        query = query.filter(
            or_(HEPSubmission.coordinator == int(user.get_id()),
                HEPSubmission.publication_recid.in_(inner_query))
        )

    return query


def get_pending_invitations_for_user(user):
    """
    Returns pending invites for upload or review of records.

    :param user: User object
    :return: array of pending invites
    """
    pending_invites = SubmissionParticipant.query.filter(
        func.lower(SubmissionParticipant.email) == func.lower(user.email),
        or_(SubmissionParticipant.role == 'reviewer',
            SubmissionParticipant.role == 'uploader'),
        SubmissionParticipant.status == 'primary',
        SubmissionParticipant.user_account == None
    ).all()

    result = []

    for invite in pending_invites:
        publication_record = get_record_by_id(invite.publication_recid)
        hepsubmission = get_latest_hepsubmission(publication_recid=invite.publication_recid)

        coordinator = get_user_from_id(hepsubmission.coordinator)
        result.append(
            {'title': decode_string(publication_record['title']),
             'invitation_cookie': invite.invitation_cookie,
             'role': invite.role, 'coordinator': coordinator})

    return result


def get_dashboard_current_user(current_user):
    """Gets the user to display in the dashboard.

    For non-admin users this will just return the current user.
    For admin users, if they have chosen to view the dashboard as another user,
    this will return that user.

    :param invenio_accounts.models.User current_user: Currently logged-in user, e.g. flask_login.current_user
    :return: User to display in the dashboard
    :rtype: invenio_accounts.models.User

    """
    user = None

    if has_role(current_user, 'admin'):
        user_id = get_session_item(VIEW_AS_USER_ID_KEY)
        if user_id and user_id != current_user.id:
            user = User.query.filter_by(id=user_id).first()

    if not user:
        user = current_user

    return user


def set_dashboard_current_user(current_user, view_as_user_id):
    user_to_display = current_user
    if view_as_user_id and view_as_user_id > 0: # -1 resets to current user
        if has_role(current_user, 'admin'):
            user_to_display = User.query.filter_by(id=view_as_user_id).first()
            if not user_to_display:
                raise ValueError(f"No user with id {view_as_user_id}")
        else:
            raise ForbiddenError()

    if view_as_user_id is not None:
        set_session_item(VIEW_AS_USER_ID_KEY, user_to_display.id)

    return user_to_display


def get_submissions_summary(user, include_imported=False, flatten_participants=True):
    """Returns the submissions for which the user is coordinator, formatted as
    a list of dictionaries.

    :param invenio_accounts.models.User user: Currently logged-in user
    :param bool include_imported: Whether to include imported records
    :param bool flatten_participants: Whether to turn participant objects into strings
    :return: List of dictionaries containing submission info
    :rtype: list[dict]

    """
    coordinator_id = None
    if not has_role(user, 'admin'):
        coordinator_id = user.id

    admin_idx = AdminIndexer()
    # Get summary data, filtering out imported records unless in TESTING mode
    return admin_idx.get_summary(
        coordinator_id=coordinator_id,
        include_imported=include_imported,
        flatten_participants=flatten_participants
    )


def get_submissions_csv(user, include_imported=False):
    """Returns the submissions for which the user is coordinator, formatted as
    a CSV string.

    :param invenio_accounts.models.User user: Currently logged-in user
    :param bool include_imported: Whether to include imported records
    :return: String containing CSV-formatted submissions
    :rtype: string
    """
    summary = get_submissions_summary(
        user,
        include_imported=include_imported,
        flatten_participants=False
    )

    si = io.StringIO()
    fieldnames = [
        'hepdata_id', 'version', 'url', 'inspire_id', 'arxiv_id',
        'title', 'collaboration', 'creation_date',
        'last_updated', 'status', 'uploaders', 'reviewers'
    ]
    writer = csv.DictWriter(si, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()

    for submission_data in summary:
        participants = submission_data.pop('participants')
        uploaders = []
        reviewers = []
        for participant in participants:
            participant_string = participant.get('email', '')
            name = participant.get('full_name')
            if name:
                participant_string += f" ({name})"

            if participant.get('role') == 'uploader':
                uploaders.append(participant_string)
            elif participant.get('role') == 'reviewer':
                reviewers.append(participant_string)

        submission_data['uploaders'] = ' | '.join(uploaders)
        submission_data['reviewers'] = ' | '.join(reviewers)
        submission_data['hepdata_id'] = submission_data['recid']
        submission_data['url'] = url_for(
            'hepdata_records.metadata',
            recid=submission_data['recid'],
            _external=True
        )
        writer.writerow(submission_data)

    return si.getvalue()
