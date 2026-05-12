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
import logging

from functools import partial
from operator import is_not

from flask_login import current_user
from sqlalchemy import or_

from hepdata.config import OBSERVER_KEY_LENGTH
from hepdata.modules.permissions.models import SubmissionParticipant, CoordinatorRequest
from hepdata.modules.records.utils.common import get_record_contents
from hepdata.modules.submission.models import HEPSubmission, SubmissionObserver
from hepdata.utils.users import get_user_from_id, user_is_admin

logging.basicConfig()
log = logging.getLogger(__name__)


def get_records_participated_in_by_user(user):
    _current_user_id = user.id

    as_uploader = SubmissionParticipant.query.filter_by(user_account=_current_user_id, role='uploader').order_by(
        SubmissionParticipant.id.desc()).all()
    as_reviewer = SubmissionParticipant.query.filter_by(user_account=_current_user_id, role='reviewer').order_by(
        SubmissionParticipant.id.desc()).all()

    as_coordinator_query = HEPSubmission.query.filter_by(coordinator=_current_user_id).order_by(
        HEPSubmission.created.desc())

    # special case, since this user ID is the one used for loading all submissions, which is in the 1000s.
    if _current_user_id == 1:
        as_coordinator_query = as_coordinator_query.limit(5)

    as_coordinator = as_coordinator_query.all()

    result = {'uploader': [], 'reviewer': [], 'coordinator': []}
    if as_uploader:
        _uploader = [get_record_contents(x.publication_recid) for x in as_uploader]
        result['uploader'] = list(filter(partial(is_not, None), _uploader))

    if as_reviewer:
        _uploader = [get_record_contents(x.publication_recid) for x in as_reviewer]
        result['reviewer'] = list(filter(partial(is_not, None), _uploader))

    if as_coordinator:
        _coordinator = [get_record_contents(x.publication_recid) for x in as_coordinator]
        result['coordinator'] = list(filter(partial(is_not, None), _coordinator))

    return result


def get_pending_request(user=current_user):
    """
    Returns True if given user has an existing request.

    :param User user: user to check. Defaults to current user.

    :return:
    """
    _user_id = int(user.get_id())

    existing_request = CoordinatorRequest.query.filter_by(
        user=_user_id, in_queue=True).all()

    return existing_request


def process_coordinators(coordinators):
    values = []
    for coordinator in coordinators:
        user = get_user_from_id(coordinator.user)
        _coordinator_dict = {'message': coordinator.message, 'id': coordinator.id,
                             'approved': coordinator.approved,
                             'in_queue': coordinator.in_queue,
                             'collaboration': coordinator.collaboration,
                             'user': {'id': user.id, 'email': user.email}}
        values.append(_coordinator_dict)
    return values


def get_pending_coordinator_requests():
    """
    Returns pending coordinator requests.

    :return:
    """
    coordinators = CoordinatorRequest.query.filter_by(
        in_queue=True).all()

    result = process_coordinators(coordinators)

    return result


def get_approved_coordinators():
    """
    Returns approved coordinator requests.

    :return:
    """
    coordinators = CoordinatorRequest.query.filter_by(
        approved=True).order_by(CoordinatorRequest.collaboration).all()

    result = process_coordinators(coordinators)

    return result


def user_allowed_to_perform_action(recid):
    """Determines if a user is allowed to perform an action on a record."""
    if not current_user.is_authenticated:
        return False

    if user_is_admin(current_user):
        return True

    is_participant = SubmissionParticipant.query.filter_by(
        user_account=int(current_user.get_id()), publication_recid=recid, status='primary').count() > 0

    if is_participant:
        return True

    is_coordinator = HEPSubmission.query.filter_by(publication_recid=recid,
                                                   coordinator=int(current_user.get_id())).count() > 0

    return is_coordinator


def write_submissions_to_files():
    """Writes some statistics on number of submissions per Coordinator to files."""

    import csv
    from datetime import datetime

    # Open a CSV file to write the number of unfinished and finished submissions for each Coordinator.
    csvfile = open('submissions_per_coordinator_{}.csv'.format(datetime.utcnow().date()), 'w')
    writer = csv.writer(csvfile)
    writer.writerow(['user_id', 'user_email', 'collaboration', 'version',
                 'number_todo', 'number_finished'])

    # Open another CSV file to write the collaboration and date of each finished version 1 submission.
    csvfile1 = open('submissions_with_date_{}.csv'.format(datetime.utcnow().date()), 'w')
    writer1 = csv.writer(csvfile1)
    writer1.writerow(['collaboration', 'publication_recid', 'inspire_id',
                  'created', 'last_updated'])

    # Loop over approved Coordinators.
    coordinators = get_approved_coordinators()
    for coordinator in coordinators:
        user_id = coordinator['user']['id']
        user_email = coordinator['user']['email']
        collaboration = coordinator['collaboration']

        # For version 1 or version 2, write number of unfinished and finished submissions.
        for version in (1, 2):
            number_todo = HEPSubmission.query.filter(
                HEPSubmission.coordinator == user_id,
                or_(HEPSubmission.overall_status == 'todo',
                    HEPSubmission.overall_status == 'processing'),
                HEPSubmission.version == version).count()
            number_finished = HEPSubmission.query.filter_by(
                coordinator=user_id,
                overall_status='finished',
                version=version).count()
            writer.writerow([user_id, user_email, collaboration,
                             version, number_todo, number_finished])

        # For each finished version 1 submission, write collaboration and date.
        submissions = HEPSubmission.query.filter_by(
                coordinator=user_id,
                overall_status='finished',
                version=1).order_by(HEPSubmission.last_updated).all()
        for submission in submissions:
            writer1.writerow([collaboration, submission.publication_recid,
                              submission.inspire_id, submission.created,
                              submission.last_updated])

    csvfile.close()
    csvfile1.close()


def verify_observer_key(submission_id, observer_key):
    """
    Verifies the access key used to access a submission without
    login requirement.
    :param int submission_id:  The requested HEPSubmission for access
    :param str observer_key: The access key used to access the submission
    :returns: Bool representing match status against database
    """

    # Validate inputs
    if submission_id is None or observer_key is None:
        return False

    try:
        submission_id = int(submission_id)
    except (ValueError, TypeError):
        log.warning(f"Invalid submission_id format: {submission_id}")
        return False

    if len(observer_key) != OBSERVER_KEY_LENGTH:
        log.warning(f"Invalid observer_key length for submission {submission_id}")
        return False
    try:
        submission_observer = SubmissionObserver.query.filter_by(
            publication_recid=submission_id,
            observer_key=observer_key
        ).first()

        result = submission_observer is not None

        return result

    except Exception as e:
        log.error(f"Database error in verify_observer_key: {e}")
        return False
