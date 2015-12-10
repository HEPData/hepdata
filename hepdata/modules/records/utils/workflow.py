from datetime import datetime
import celery
from flask import render_template
from hepdata.modules.records.models import SubmissionParticipant, \
    DataSubmission
from invenio_db import db

__author__ = 'eamonnmaguire'


@celery.task
def create_bibworkflow_obj(ctx, current_user_id, doc_type,
                           workflow="hepdata_data_sub"):
    record = {
        "type": "hepdata_data_sub",
        "title": ctx["name"],
        "completed": True, "files": [],
        "drafts": {
            "values": {
                "title": ctx["name"],
                "abstract": ctx["description"],
                "type_of_doc": doc_type,

                "flags": {},
                "validate": False,
                "completed": True,
                "authors": ctx["authors"],
                "all_authors": ctx["authors"],
                "values": {
                    "title": ctx["name"],
                    "abstract": ctx["description"],
                    "inspire_id": ctx["inspire_id"],
                    "_first_author": ctx["_first_author"],
                    "_additional_authors": [],
                    "authors": ctx["authors"],
                    "all_authors": []
                },
            }
        }
    }

    optional_keys = ["related_publication", "recid", "keywords",
                     "control_number", "doi", "creation_date",
                     "last_updated", "data_endpoints", "collaborations",
                     "journal_info"]

    for key in optional_keys:
        if key in ctx:
            record["drafts"]["values"][key] = ctx[key]
            record["drafts"]["values"]["values"][key] = ctx[key]

            if "recid" == key:
                record[key] = ctx[key]

        # myobj = BibWorkflowObject.create_object(id_user=current_user_id)
        # myobj.set_data(record)
        # myobj.start_workflow(workflow)


def update_action_for_submission_participant(recid, user_id, action):
    SubmissionParticipant.query.filter_by(
        publication_recid=recid, role=action, user_account=user_id)\
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

    table_information = DataSubmission.query\
        .filter_by(id=review.data_recid).one()

    for participant in submission_participants:
        message = render_template(
            'hepdata_dashboard/email/review-message.html',
            name=participant.full_name,
            actor=user.nickname,
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
                                  actor=user.nickname,
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
        send_email(SITE_ADMIN_EMAIL,
                   email,
                   header="",
                   subject=subject,
                   content=message)
    except Exception as e:
        print e.message
