from datetime import datetime
import uuid
from celery import shared_task
from flask import render_template
from invenio_pidstore.minters import recid_minter
from invenio_records import Record
from hepdata.modules.records.models import SubmissionParticipant, \
    DataSubmission
from invenio_db import db

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
        print ctx.get('title')
        title = ctx.get('title')[0]

    record = {"title": title,
              "abstract": ctx.get('abstract'),
              "inspire_id": ctx.get("inspire_id"),
              "_first_author": ctx.get("_first_author"),
              "authors": ctx.get("authors")
              }

    optional_keys = ["related_publication", "recid", "keywords",
                     "control_number", "doi", "creation_date",
                     "last_updated", "data_endpoints", "collaborations",
                     "journal_info", "uploaders", "reviewers"]

    for key in optional_keys:
        if key in ctx:
            record[key] = ctx[key]

            if "recid" == key:
                record[key] = ctx[key]

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

    for participant in submission_participants:
        message = render_template(
            'hepdata_dashboard/email/review-message.html',
            name=participant.full_name,
            actor=user.email,
            table_name=table_information.name,
            table_message=message.message,
            article=review.publication_recid,
            link="http://hepdata.net/record/{0}"
                .format(review.publication_recid))

        do_send_email('[HEPData] Submission {0} has a new upload available '
                      'for your review.'
                      .format(review.publication_recid),
                      message, participant.email)


def send_new_upload_email(recid, user):
    """
    :param action: e.g. upload or review_message
    :param hepsubmission: submission information
    :param user: user object
    :return:
    """

    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=recid, status="primary", role="reviewer")

    for participant in submission_participants:
        message = render_template('hepdata_dashboard/email/upload.html',
                                  name=participant.full_name,
                                  actor=user.email,
                                  article=recid,
                                  link="http://hepdata.net/record/{0}"
                                  .format(recid))

        do_send_email('[HEPData] Submission {0} has a '
                      'new upload available for you to review.'
                      .format(recid), message, participant.email)


def send_finalised_email(hepsubmission):
    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=hepsubmission.publication_recid, status="primary")

    for participant in submission_participants:
        message = render_template('hepdata_dashboard/email/finalised.html',
                                  name=participant.full_name,
                                  article=hepsubmission.publication_recid,
                                  version=hepsubmission.latest_version,
                                  link="http://hepdata.net/record/{0}"
                                  .format(hepsubmission.publication_recid))

        do_send_email('[HEPData] Submission {0} has been finalised and is '
                      'publicly available.'
                      .format(hepsubmission.publication_recid), message,
                      participant.email)


def do_send_email(subject, message, email):
    """
    General function to send an email with the subject,
    message and email for the participant
    :param hepsubmission:
    :param message:
    :param email:
    :return:
    """
    try:
        print message
        # send_email('info@hepdata.net',
        #            email,
        #            header="",
        #            subject=subject,
        #            content=message)
    except Exception as e:
        print e.message
