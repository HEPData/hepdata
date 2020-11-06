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

from invenio_accounts.models import User

from sqlalchemy import and_, or_, func

from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.common import get_record_by_id, decode_string
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.records.utils.users import has_role
from hepdata.modules.submission.models import HEPSubmission, DataReview
from hepdata.utils.users import get_user_from_id


def add_user_to_metadata(type, user_info, record_id, submissions):
    if user_info:
        submissions[record_id]["metadata"][type] = {
            'name': user_info['full_name'],
            'email': user_info['email']}
    else:
        submissions[record_id]["metadata"][type] = {
            'name': 'No primary ' + type}


def create_record_for_dashboard(record_id, submissions, current_user, coordinator=None, user_role=None,
                                status="todo"):
    if user_role is None:
        user_role = ["coordinator"]

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


def get_submission_count(current_user):
    query = _prepare_submission_query(current_user)
    return query.count()


def prepare_submissions(current_user, items_per_page=25, current_page=1, record_id=None):
    """
    Finds all the relevant submissions for a user, or all submissions if the logged in user is a 'super admin'.

    :param current_user: User obj
    :param items_per_page: maximum number of items to return
    :param current_page: page of current set of results (starting at 1)
    :return: OrderedDict of submissions
    """

    submissions = OrderedDict()

    query = _prepare_submission_query(current_user)

    if record_id:
        query = query.filter(HEPSubmission.publication_recid == record_id)

    offset = (current_page - 1) * items_per_page

    hepdata_submission_records = query.order_by(
        HEPSubmission.last_updated.desc()
    ).limit(items_per_page).offset(offset).all()

    for hepdata_submission in hepdata_submission_records:

        if str(hepdata_submission.publication_recid) not in submissions:

            coordinator = User.query.get(hepdata_submission.coordinator)

            if hepdata_submission.participants:
                current_user_roles = []

                for participant in hepdata_submission.participants:

                    if int(current_user.get_id()) == participant.user_account:
                        current_user_roles.append(participant.role)

                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    current_user,
                    coordinator=coordinator,
                    user_role=current_user_roles,
                    status=hepdata_submission.overall_status)
            else:
                create_record_for_dashboard(
                    str(hepdata_submission.publication_recid), submissions,
                    current_user,
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
    query = _prepare_submission_query(current_user)

    hepdata_submission_records = query.order_by(
        HEPSubmission.last_updated.desc()
    ).all()

    titles = []
    for hepsubmission in hepdata_submission_records:
        publication_record = get_record_by_id(int(hepsubmission.publication_recid))
        titles.append({
            'id': int(hepsubmission.publication_recid),
            'title': publication_record['title']
        })

    return titles


def _prepare_submission_query(current_user):
    query = HEPSubmission.query.filter(
        HEPSubmission.overall_status.in_(['processing', 'todo']),
    )

    # if the user is a superadmin, show everything here.
    # The final rendering in the dashboard should be different
    # though considering the user him/herself is probably not a
    # reviewer/uploader
    if not has_role(current_user, 'admin'):
        # Not an admin user
        # We just want to pick out people with access to particular records,
        # i.e. submissions for which they are primary reviewers or coordinators.

        inner_query = SubmissionParticipant.query.filter_by(
            user_account=int(current_user.get_id()),
            status='primary'
        ).with_entities(
            SubmissionParticipant.publication_recid
        )

        query.filter(
            or_(HEPSubmission.coordinator == int(current_user.get_id()),
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
