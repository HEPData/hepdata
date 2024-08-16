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
from invenio_userprofiles import UserProfile

from hepdata.modules.email.utils import create_send_email_task
from hepdata.modules.records.subscribers.api import get_users_subscribed_to_record
from hepdata.modules.records.utils.common import get_record_by_id
from flask import render_template

from hepdata.modules.permissions.models import CoordinatorRequest
from hepdata.modules.submission.api import get_latest_hepsubmission, \
    get_primary_submission_participants_for_record, get_submission_participants_for_record
from hepdata.modules.submission.models import HEPSubmission, DataSubmission, DataReview
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
    submission_participants = get_primary_submission_participants_for_record(review.publication_recid)

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
        message_body,
        user.email
    )


class NoParticipantsException(Exception):
    pass


def send_notification_email(recid, version, user, reviewers_notified, message=None, show_detail=True):
    """
    :param recid:
    :param user: user object
    :param reviewers_notified: whether reviewers have already been notified about this upload
    :param show_detail: whether to show the status and messages for each data table
    :param message:
    :return:
    """

    submission_participants = get_submission_participants_for_record(
        recid, roles=['uploader', 'reviewer'], status='primary'
    )

    if len(submission_participants) == 0:
        raise NoParticipantsException()

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    record = get_record_by_id(recid)

    tables = []
    if show_detail:
        data_submissions = DataSubmission.query.filter_by(
            publication_recid=recid,
            version=version
        )

        for data_submission in data_submissions:
            table_data = {
                'name': data_submission.name,
                'status': 'todo'
            }
            review = DataReview.query.filter_by(
                publication_recid=recid, data_recid=data_submission.id, version=version
            ).first()
            if review:
                table_data['status'] = review.status
                table_data['messages'] = []
                for m in review.messages:
                    table_data['messages'].append({
                        'user': get_user_from_id(m.user).email,
                        'date': m.creation_date.strftime("%Y-%m-%d at %H:%M UTC"),
                        'message': m.message
                    })

            tables.append(table_data)

    for participant in submission_participants:
        invite_token = None
        if not participant.user_account:
            invite_token = participant.invitation_cookie

        message_body = render_template('hepdata_theme/email/submission_status.html',
                                       name=participant.full_name,
                                       actor=user.email,
                                       article=recid,
                                       message=message,
                                       invite_token=invite_token,
                                       role=participant.role,
                                       show_detail=show_detail,
                                       data_tables=tables,
                                       reviewers_notified=reviewers_notified,
                                       title=record['title'],
                                       site_url=site_url,
                                       reminder=False,
                                       link=site_url + "/record/{0}"
                                       .format(recid))

        if participant.role == 'reviewer' and not reviewers_notified:
            message_subject = '[HEPData] Submission {0} has a new upload available for you to review'.format(recid)
            hepsubmission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).one()
            coordinator = User.query.get(hepsubmission.coordinator)
        else:
            message_subject = '[HEPData] Notification about submission {0}'.format(recid)

        create_send_email_task(participant.email,
                               message_subject,
                               message_body,
                               reply_to_address=user.email)


def send_coordinator_notification_email(recid, version, user, message=None):
    """
    :param recid:
    :param user: user object
    :param message: message to send
    :return:
    """

    hepsubmission = get_latest_hepsubmission(publication_recid=recid)
    coordinator = get_user_from_id(hepsubmission.coordinator)

    if not coordinator:
        raise NoParticipantsException()

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    record = get_record_by_id(recid)

    name = coordinator.email
    coordinator_profile = UserProfile.get_by_userid(hepsubmission.coordinator)
    if coordinator_profile and coordinator_profile.user_profile and coordinator_profile.full_name:
        name = coordinator_profile.full_name

    collaboration = _get_collaboration(hepsubmission.coordinator)

    message_body = render_template('hepdata_theme/email/passed_review.html',
                                   name=name,
                                   actor=user.email,
                                   collaboration=collaboration,
                                   article=recid,
                                   version=version,
                                   message=message,
                                   title=record['title'],
                                   site_url=site_url,
                                   link=site_url + "/record/{0}".format(recid),
                                   dashboard_link=site_url + "/dashboard"
                                   )

    create_send_email_task(coordinator.email,
                           '[HEPData] Submission {0} is ready to be finalised'.format(recid),
                           message_body,
                           reply_to_address=user.email)


def send_finalised_email(hepsubmission):

    record = get_record_by_id(hepsubmission.publication_recid)

    notify_participants(hepsubmission, record)
    notify_subscribers(hepsubmission, record)


def notify_participants(hepsubmission, record):

    destinations = []
    coordinator = User.query.get(hepsubmission.coordinator)
    if coordinator.id > 1:
        destinations.append(coordinator.email)
    submission_participants = get_primary_submission_participants_for_record(hepsubmission.publication_recid)
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
                           message_body,
                           reply_to_address=coordinator.email)


def notify_subscribers(hepsubmission, record):
    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
    subscribers = get_users_subscribed_to_record(hepsubmission.publication_recid)
    coordinator = User.query.get(hepsubmission.coordinator)
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
                               message_body,
                               reply_to_address=coordinator.email)


def send_cookie_email(submission_participant,
                      record_information, message=None, version=1):

    hepsubmission = get_latest_hepsubmission(
        publication_recid=record_information['recid']
    )
    coordinator = User.query.get(hepsubmission.coordinator)
    collaboration = _get_collaboration(hepsubmission.coordinator)

    message_body = render_template(
        'hepdata_theme/email/invite.html',
        name=submission_participant.full_name,
        role=submission_participant.role,
        title=record_information['title'],
        site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
        user_account=submission_participant.user_account,
        invite_token=submission_participant.invitation_cookie,
        status=submission_participant.status,
        recid=submission_participant.publication_recid,
        version=version,
        email=submission_participant.email,
        coordinator_email=coordinator.email,
        collaboration=collaboration,
        message=message)

    create_send_email_task(submission_participant.email,
                           "[HEPData] Invitation to be {0} {1} of record {2} in HEPData".format(
                               "an" if submission_participant.role == "uploader" else "a",
                               submission_participant.role.capitalize(),
                               submission_participant.publication_recid),
                           message_body,
                           reply_to_address=coordinator.email)

def send_reminder_email(submission_participant, record_information, version, show_detail=False, message=None):
    """
    Sends an email reminder to either an uploader, or reviewer.

    :param submission_participant: A SubmissionParticipant object, to receive the email reminder
    :param record_information: Record object containing record information
    :param version: The record version
    :param show_detail: Optionally includes specific detail for each table in the submission (default is False)
    :param message: Any specific message text input into the form (Default is None)
    """
    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
    tables = []
    hepsubmission = get_latest_hepsubmission(
        publication_recid=record_information['recid']
    )
    coordinator = User.query.get(hepsubmission.coordinator)

    reviewers_notified = submission_participant.user_account is not None

    message_body = render_template('hepdata_theme/email/submission_status.html',
                                   name=submission_participant.full_name,
                                   actor=coordinator.email,
                                   article=record_information['recid'],
                                   message=message,
                                   invite_token=submission_participant.invitation_cookie,
                                   role=submission_participant.role,
                                   show_detail=show_detail,
                                   data_tables=tables,
                                   reviewers_notified=reviewers_notified,
                                   title=record_information['title'],
                                   site_url=site_url,
                                   reminder=True,
                                   link=site_url + "/record/{0}"
                                   .format(record_information['recid']))

    if not reviewers_notified:
        message_subject = '[HEPData] Reminder to review submission {0}'.format(record_information['recid'])
    else:
        message_subject = '[HEPData] Reminder about submission {0}'.format(record_information['recid'])

    create_send_email_task(submission_participant.email,
                           message_subject,
                           message_body,
                           reply_to_address=coordinator.email)


def send_reserve_email(submission_participant, record_information):

    hepsubmission = get_latest_hepsubmission(
        publication_recid=record_information['recid']
    )
    coordinator = User.query.get(hepsubmission.coordinator)
    collaboration = _get_collaboration(hepsubmission.coordinator)

    message_body = render_template(
        'hepdata_theme/email/reserve.html',
        name=submission_participant.full_name,
        role=submission_participant.role,
        title=record_information['title'],
        site_url=current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
        recid=submission_participant.publication_recid,
        email=submission_participant.email,
        coordinator_email=coordinator.email,
        collaboration=collaboration)

    create_send_email_task(submission_participant.email,
                           "[HEPData] Change of {0} status for record {1} in HEPData".format(
                               submission_participant.role.capitalize(),
                               submission_participant.publication_recid),
                           message_body,
                           reply_to_address=coordinator.email)


def send_question_email(question):
    reply_to = current_user.email

    submission = get_latest_hepsubmission(publication_recid=question.publication_recid)
    submission_participants = get_primary_submission_participants_for_record(question.publication_recid)

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
                               message=message_body,
                               reply_to_address=current_user.email)


def notify_publication_update(hepsubmission, record):

    destinations = []
    coordinator = User.query.get(hepsubmission.coordinator)
    if coordinator.id > 1:
        destinations.append(coordinator.email)
    submission_participants = get_primary_submission_participants_for_record(hepsubmission.publication_recid)
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


def notify_submission_created(record, coordinator_id, uploader, reviewer):
    coordinator = get_user_from_id(coordinator_id)

    if not coordinator:
        return

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    name = coordinator.email
    coordinator_profile = UserProfile.get_by_userid(coordinator_id)
    if coordinator_profile and coordinator_profile.user_profile and coordinator_profile.full_name:
        name = coordinator_profile.full_name

    collaboration = _get_collaboration(coordinator_id)

    message_body = render_template('hepdata_theme/email/created.html',
                                   name=name,
                                   actor=coordinator.email,
                                   collaboration=collaboration,
                                   uploader=uploader,
                                   reviewer=reviewer,
                                   article=record['recid'],
                                   title=record['title'],
                                   site_url=site_url,
                                   link=site_url + "/record/{0}".format(record['recid']))

    create_send_email_task(coordinator.email,
                           '[HEPData] Submission {0} has been created'.format(record['recid']),
                           message_body)


def _get_collaboration(coordinator_id):
    coordinator_request = CoordinatorRequest.query.filter_by(
        user=coordinator_id, approved=True).first()
    if coordinator_request:
        collaboration = coordinator_request.collaboration
    else:
        collaboration = None
    return collaboration
