from flask import Blueprint, render_template, request, jsonify
from flask.ext.login import login_required, current_user
from invenio_db import db

from hepdata.modules.email.api import send_cookie_email
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.submission import \
    get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record

__author__ = 'eamonnmaguire'

blueprint = Blueprint(
    'submission',
    __name__,
    url_prefix='/submit',
    template_folder='templates',
    static_folder='static'
)


@login_required
@blueprint.route('', methods=['GET'])
def submit_ui():
    return render_template('hepdata_submission/submit.html')


@login_required
@blueprint.route('', methods=['POST'])
def submit_post():
    inspire_id = request.form['inspire_id']
    title = request.form['title']
    reviewer_str = request.form['reviewer']
    uploader_str = request.form['uploader']
    message = request.form['message']

    reviewer = parse_person_string(reviewer_str)[0]
    uploader = parse_person_string(uploader_str)[0]

    hepdata_submission = process_submission_payload(inspire_id=inspire_id,
                                                    title=title,
                                                    reviewer=reviewer,
                                                    uploader=uploader, message=message)

    if hepdata_submission:
        return jsonify({'success': True, 'message': 'Submission successful.'})
    else:
        return jsonify({'success': False, 'message': 'Submission unsuccessful.'})


def process_submission_payload(*args, **kwargs):
    """
    Processes the submission payload
    :param inspire_id:
    :param title:
    :param reviewer:
    :param uploader:
    :param send_upload_email:
    :return:
    """
    if kwargs.get('inspire_id'):
        content, status = get_inspire_record_information(kwargs.get('inspire_id'))
        content["inspire_id"] = kwargs.get('inspire_id')
    elif kwargs.get('title'):
        content = {'title': kwargs.get('title')}
    else:
        raise ValueError(message="A title or inspire_id must be provided.")

    record_information = create_record(content)
    submitter_id = kwargs.get('submitter_id')
    if submitter_id is None:
        submitter_id = int(current_user.get_id())

    hepsubmission = get_or_create_hepsubmission(record_information["recid"], submitter_id)

    reviewer_details = kwargs.get('reviewer')

    reviewer = create_participant_record(
        reviewer_details.get('name'),
        reviewer_details.get('email'), 'reviewer', 'primary',
        record_information['recid'])
    hepsubmission.participants.append(reviewer)

    uploader_details = kwargs.get('uploader')
    uploader = create_participant_record(uploader_details.get('name'), uploader_details.get('email'),
                                         'uploader', 'primary',
                                         record_information['recid'])
    hepsubmission.participants.append(uploader)

    db.session.commit()

    if kwargs.get('send_upload_email', True):
        # Now Send Email only to the uploader first. The reviewer will be asked to
        # review only when an upload has been performed.
        message = kwargs.get('message', None)
        send_cookie_email(uploader, record_information, message)

    return hepsubmission


def create_participant_record(name, email, role, status, recid):
    participant_record = SubmissionParticipant(full_name=name,
                                               email=email,
                                               status=status,
                                               role=role,
                                               publication_recid=recid)

    return participant_record


def parse_person_string(person_string, separator="::"):
    """
    Parses a string in the format name::email in to separate parts
    :param person_string: e.g. John::j.p.a@cern.ch
    :param separator: by default '::'
    :return: name, email
    """

    if separator in person_string:
        string_parts = person_string.split(separator)
        return {'name': string_parts[0], 'email': string_parts[1]},

    return {'name': person_string, 'email': person_string}

