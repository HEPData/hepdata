from datetime import datetime
import uuid

import jsonpatch
from flask import render_template
from invenio_pidstore.minters import recid_minter
from invenio_records import Record
from hepdata.modules.records.models import SubmissionParticipant, \
    DataSubmission
from invenio_db import db

from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.utils.mail import create_send_email_task

__author__ = 'eamonnmaguire'


def create_data_structure(ctx):
    """
    The data structures need to be normalised before being stored in
    the database. This is performed here.
    :param ctx: record information as a dictionary
    :return: a cleaned up representation.
    """

    title = ctx.get('title')
    if type(ctx.get('title')) is list and len(ctx.get('title')) > 0:
        title = ctx.get('title')[0]

    first_author = {}
    authors = ctx.get('authors', [])
    if authors is not None and len(authors) > 0:
        first_author = authors[0]

    record = {"title": title,
              "abstract": ctx.get('abstract'),
              "inspire_id": ctx.get("inspire_id"),
              "first_author": first_author,
              "authors": authors
              }

    optional_keys = ["related_publication", "recid", "keywords", "dissertation", "type",
                     "control_number", "doi", "creation_date", "year", "hepdata_doi",
                     "last_updated", "data_endpoints", "collaborations",
                     "journal_info", "uploaders", "reviewers"]

    for key in optional_keys:
        if key in ctx:
            record[key] = ctx[key]

            if "recid" == key:
                record[key] = ctx[key]

    return record


def update_record(recid, ctx):
    """
    Updates a record given a new dictionary.
    :param recid:
    :param ctx:
    :return:
    """
    print 'Recid is {}'.format(recid)
    record = get_record_by_id(recid)
    for key, value in ctx.iteritems():
        record[key] = value

    record.commit()
    db.session.commit()

    return record


def create_record(ctx):
    """
    Creates the record in the database.
    :param ctx: The record metadata as a dictionary.
    :return: the recid and the uuid
    """
    record_information = create_data_structure(ctx)
    record_id = uuid.uuid4()
    pid = recid_minter(record_id, record_information)
    record_information['recid'] = int(pid.pid_value)
    record_information['uuid'] = str(record_id)

    Record.create(record_information, id_=record_id)
    db.session.commit()

    return record_information


def update_action_for_submission_participant(recid, user_id, action):
    SubmissionParticipant.query.filter_by(
        publication_recid=recid, role=action, user_account=user_id) \
        .update(dict(action_date=datetime.now()))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def send_new_review_message_email(review, message, user):
    """
    Sends a message to all uploaders to tell them that a
    comment has been made on a record
    :param hepsubmission:
    :param review:
    :param user:
    :return:
    """
    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=review.publication_recid,
        status="primary", role="uploader")

    table_information = DataSubmission.query \
        .filter_by(id=review.data_recid).one()

    record = get_record_by_id(review.publication_recid)

    for participant in submission_participants:
        message_body = render_template(
            'hepdata_dashboard/email/review-message.html',
            name=participant.full_name,
            actor=user.email,
            table_name=table_information.name,
            table_message=message.message,
            article=review.publication_recid,
            title=record['title'],
            link="http://hepdata.net/record/{0}"
                .format(review.publication_recid))

        create_send_email_task(
            participant.email,
            '[HEPData] Submission {0} has a new review message.' \
                .format(review.publication_recid), message_body)


class NoReviewersException(Exception):
    pass


def send_new_upload_email(recid, user, message=None):
    """
    :param action: e.g. upload or review_message
    :param hepsubmission: submission information
    :param user: user object
    :return:
    """

    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=recid, status="primary", role="reviewer")

    if submission_participants.count() == 0:
        raise NoReviewersException()

    record = get_record_by_id(recid)

    for participant in submission_participants:
        message_body = render_template('hepdata_dashboard/email/upload.html',
                                       name=participant.full_name,
                                       actor=user.email,
                                       article=recid,
                                       message=message,
                                       title=record['title'],
                                       link="http://hepdata.net/record/{0}"
                                       .format(recid))

        create_send_email_task(participant.email,
                               '[HEPData] Submission {0} has a new upload available for you to review.'.format(recid),
                               message_body)


def send_finalised_email(hepsubmission):
    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=hepsubmission.publication_recid, status="primary")

    record = get_record_by_id(hepsubmission.publication_recid)

    for participant in submission_participants:
        message_body = render_template(
            'hepdata_dashboard/email/finalised.html',
            name=participant.full_name,
            article=hepsubmission.publication_recid,
            version=hepsubmission.version,
            title=record['title'],
            link="http://hepdata.net/record/{0}"
                .format(hepsubmission.publication_recid))

        create_send_email_task(participant.email,
                               '[HEPData] Submission {0} has been finalised and is publicly available' \
                               .format(hepsubmission.publication_recid),
                               message_body)
