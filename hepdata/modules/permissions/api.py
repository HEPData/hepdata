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


from functools import partial
from operator import is_not

from flask.ext.login import current_user

from hepdata.modules.permissions.models import SubmissionParticipant, CoordinatorRequest
from hepdata.modules.records.utils.common import get_record_contents
from hepdata.modules.submission.models import HEPSubmission
from hepdata.utils.users import get_user_from_id, user_is_admin


def get_records_participated_in_by_user():
    _current_user_id = int(current_user.get_id())
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
        result['uploader'] = filter(partial(is_not, None), _uploader)

    if as_reviewer:
        _uploader = [get_record_contents(x.publication_recid) for x in as_reviewer]
        result['reviewer'] = filter(partial(is_not, None), _uploader)

    if as_coordinator:
        _coordinator = [get_record_contents(x.publication_recid) for x in as_coordinator]
        result['coordinator'] = filter(partial(is_not, None), _coordinator)

    return result


def get_pending_request():
    """
    Returns True is current user has an existing request.
    :return:
    """
    _current_user_id = int(current_user.get_id())

    existing_request = CoordinatorRequest.query.filter_by(
        user=_current_user_id, in_queue=True).all()

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
    Returns pending coordinator requests
    :return:
    """
    coordinators = CoordinatorRequest.query.filter_by(
        in_queue=True).all()

    result = process_coordinators(coordinators)

    return result


def get_approved_coordinators():
    """
    Returns pending coordinator requests
    :return:
    """
    coordinators = CoordinatorRequest.query.filter_by(
        approved=True).order_by(CoordinatorRequest.collaboration).all()

    result = process_coordinators(coordinators)

    return result


def user_allowed_to_perform_action(recid):
    """Determines if a user is allowed to perform an action on a record"""
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
