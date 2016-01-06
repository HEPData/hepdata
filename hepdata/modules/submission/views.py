from flask import Blueprint, render_template, request, jsonify
from flask.ext.login import login_required, current_user
from invenio_db import db
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.records.models import SubmissionParticipant
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
    reviewer = request.form['reviewer']
    uploader = request.form['uploader']

    if inspire_id:
        content, status = get_inspire_record_information(inspire_id)
        content["inspire_id"] = inspire_id
    else:
        content = {'name': title}

    record_information = create_record(content)
    get_or_create_hepsubmission(record_information["recid"],
                                int(current_user.get_id()))

    reviewer_name, reviewer_email = parse_person_string(reviewer)
    uploader_name, uploader_email = parse_person_string(uploader)

    create_participant_record(reviewer_name, reviewer_email, 'reviewer',
                              'primary', record_information['recid'])

    create_participant_record(uploader_name, uploader_email, 'uploader',
                              'primary', record_information['recid'])

    return jsonify({'success': True, 'message': 'Submission successful.'})


def create_participant_record(name, email, role, status, recid):
    participant_record = SubmissionParticipant(full_name=name,
                                               email=email,
                                               status=status,
                                               role=role,
                                               publication_recid=recid)

    db.session.add(participant_record)
    db.session.commit()


def parse_person_string(person_string, separator="::"):
    """
    Parses a string in the format name::email in to separate parts
    :param person_string: e.g. John::j.p.a@cern.ch
    :param separator: by default '::'
    :return: name, email
    """

    if separator in person_string:
        string_parts = person_string.split(separator)
        return string_parts[0], string_parts[1]

    return person_string
