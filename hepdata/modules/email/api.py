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

"""Email API provides all email functions for HEPData."""
import logging

from flask import current_app
from flask_login import current_user

from hepdata.modules.email.utils import create_send_email_task
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.subscribers.api import get_users_subscribed_to_record
from hepdata.modules.records.utils.common import get_record_by_id
from flask import render_template

from hepdata.modules.submission.api import get_latest_hepsubmission, get_submission_participants_for_record
from hepdata.modules.submission.models import DataSubmission
from hepdata.utils.users import get_user_from_id
from invenio_accounts.models import User

logging.basicConfig()
log = logging.getLogger(__name__)


def send_new_review_message_email(review, message, user):
    """
    Sends a message to all uploaders and reviewers to tell them that a
    comment has been made on a record.

    :param review:
    :param message:
    :param user:
    :return:
    """
    submission_participants = get_submission_participants_for_record(review.publication_recid)

    table_information = DataSubmission.query.filter_by(id=review.data_recid).one()

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    record = get_record_by_id(review.publication_recid)

    destinations = [participant.email for participant in submission_participants]
    full_names = [participant.full_name for participant in submission_participants]

    message_body = render_template(
        'hepdata_theme/email/review-message.html',
        name=', '.join(set(full_names)),
        actor=user.email,
        table_name=table_information.name,
        table_message=message.message,
        article=review.publication_recid,
        title=record['title'],
        site_url=site_url,
        link=site_url + "/record/{0}".format(review.publication_recid),
        table_link=site_url + "/record/{0}?table={1}".format(
            review.publication_recid, table_information.name.replace('+', '%2B'))
    )

    create_send_email_task(
        ','.join(set(destinations)),
        '[HEPData] Submission {0} ({1}) has a new review message'.format(
            review.publication_recid, table_information.name),
        message_body
    )


class NoReviewersException(Exception):
    pass


def send_new_upload_email(recid, user, message=None):
    """
    :param recid:
    :param user: user object
    :param message:
    :return:
    """

    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=recid, status="primary", role="reviewer")

    if submission_participants.count() == 0:
        raise NoReviewersException()

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    record = get_record_by_id(recid)

    for participant in submission_participants:
        invite_token = None
        if not participant.user_account:
            invite_token = participant.invitation_cookie

        message_body = render_template('hepdata_theme/email/upload.html',
                                       name=participant.full_name,
                                       actor=user.email,
                                       article=recid,
                                       message=message,
                                       invite_token=invite_token,
                                       role=participant.role,
                                       title=record['title'],
                                       site_url=site_url,
                                       link=site_url + "/record/{0}"
                                       .format(recid))

        create_send_email_task(participant.email,
                               '[HEPData] Submission {0} has a new upload available for you to review'.format(recid),
                               message_body)


def send_finalised_email(hepsubmission):

    record = get_record_by_id(hepsubmission.publication_recid)

    notify_participants(hepsubmission, record)
    notify_subscribers(hepsubmission, record)


def notify_participants(hepsubmission, record):

    destinations = []
    coordinator = User.query.get(hepsubmission.coordinator)
    if coordinator.id > 1:
        destinations.append(coordinator.email)
    submission_participants = get_submission_participants_for_record(hepsubmission.publication_recid)
    for participant in submission_participants:
        destinations.append(participant.email)
    if not destinations:
        destinations.append(current_app.config['ADMIN_EMAIL'])

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    message_body = render_template(
        'hepdata_theme/email/finalised.html',
        article=hepsubmission.publication_recid,
        version=hepsubmission.version,
        title=record['title'],
        site_url=site_url,
        link=site_url + "/record/ins{0}?version={1}"
        .format(hepsubmission.inspire_id, hepsubmission.version))

    create_send_email_task(','.join(set(destinations)),
                           '[HEPData] Submission {0} has been finalised and is publicly available'
                           .format(hepsubmission.publication_recid),
                           message_body)


def notify_subscribers(hepsubmission, record):
    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
    subscribers = get_users_subscribed_to_record(hepsubmission.publication_recid)
    for subscriber in subscribers:
        message_body = render_template(
            'hepdata_theme/email/subscriber_notification.html',
            article=hepsubmission.publication_recid,
            version=hepsubmission.version,
            title=record['title'],
            site_url=site_url,
            link=site_url + "/record/ins{0}?version={1}"
                .format(hepsubmission.inspire_id, hepsubmission.version))

        create_send_email_task(subscriber.get('email'),
                               '[HEPData] Record update available for submission {0}'
                               .format(hepsubmission.publication_recid),
                               message_body)


def send_cookie_email(submission_participant,
                      record_information, message=None):
    message_body = render_template(
        'hepdata_theme/email/invite.html',
        name=submission_participant.full_name,
        role=submission_participant.role,
        title=record_information['title'],
        site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
        invite_token=submission_participant.invitation_cookie,
        recid=submission_participant.publication_recid,
        email=submission_participant.email,
        message=message)

    create_send_email_task(submission_participant.email,
                           "[HEPData] Invitation to be a {0} of record {1} in HEPData".format(
                               submission_participant.role,
                               submission_participant.publication_recid), message_body)


def send_question_email(question):
    reply_to = current_user.email

    submission = get_latest_hepsubmission(publication_recid=question.publication_recid)
    submission_participants = get_submission_participants_for_record(question.publication_recid)

    if submission:
        destinations = [current_app.config['ADMIN_EMAIL']]
        for submission_participant in submission_participants:
            destinations.append(submission_participant.email)

        coordinator = User.query.get(submission.coordinator)
        if coordinator.id > 1:
            destinations.append(coordinator.email)

        if len(destinations) > 0:
            message_body = render_template(
                'hepdata_theme/email/question.html',
                inspire_id=submission.inspire_id,
                user_email=reply_to,
                site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
                message=question.question)

            create_send_email_task(destination=','.join(set(destinations)),
                                   subject="[HEPData] Question for record ins{0}".format(submission.inspire_id),
                                   message=message_body, reply_to_address=reply_to)


def send_coordinator_request_mail(coordinator_request):
    if current_user.is_authenticated:
        message_body = render_template(
            'hepdata_theme/email/coordinator_request.html',
            collaboration=coordinator_request.collaboration,
            message=coordinator_request.message,
            user_email=current_user.email,
            site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net')
        )

        create_send_email_task(current_app.config['ADMIN_EMAIL'],
                               subject="[HEPData] New Coordinator Request",
                               message=message_body, reply_to_address=current_user.email)
    else:
        log.error('Current user is not authenticated.')


def send_coordinator_approved_email(coordinator_request):
    message_body = render_template(
        'hepdata_theme/email/coordinator_approved.html',
        collaboration=coordinator_request.collaboration,
        message=coordinator_request.message,
        user_email=current_user.email,
        site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net')
    )

    user = get_user_from_id(coordinator_request.user)
    if user:
        create_send_email_task(user.email,
                               subject="[HEPData] Coordinator Request Approved",
                               message=message_body)


def notify_publication_update(hepsubmission, record):

    destinations = []
    coordinator = User.query.get(hepsubmission.coordinator)
    if coordinator.id > 1:
        destinations.append(coordinator.email)
    submission_participants = get_submission_participants_for_record(hepsubmission.publication_recid)
    for participant in submission_participants:
        destinations.append(participant.email)
    if not destinations:
        destinations.append(current_app.config['ADMIN_EMAIL'])

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    message_body = render_template(
        'hepdata_theme/email/publication_update.html',
        inspire_id=hepsubmission.inspire_id,
        title=record['title'],
        site_url=site_url,
        link=site_url + "/record/ins{0}"
        .format(hepsubmission.inspire_id))

    create_send_email_task(','.join(set(destinations)),
                           '[HEPData] Record ins{0} has updated publication information from INSPIRE'
                           .format(hepsubmission.inspire_id),
                           message_body)
