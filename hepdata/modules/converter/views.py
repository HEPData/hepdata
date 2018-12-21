#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#
from __future__ import absolute_import, print_function
import logging
import os

from celery import shared_task
from flask import Blueprint, send_file, render_template, \
    request, current_app, redirect, abort
import time
from werkzeug.utils import secure_filename
from hepdata.config import CFG_CONVERTER_URL, CFG_SUPPORTED_FORMATS

from hepdata_converter_ws_client import convert
from hepdata.modules.permissions.api import user_allowed_to_perform_action
from hepdata.modules.converter import convert_zip_archive
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission, DataResource, DataSubmission
from hepdata.utils.file_extractor import extract, get_file_in_directory
from hepdata.modules.records.utils.common import get_record_contents

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint('converter', __name__,
                      url_prefix="/download",
                      template_folder='templates',
                      static_folder='static')


@blueprint.route('/convert', methods=['GET', 'POST'])
def convert_endpoint():
    """ Endpoint for general conversion, the file is passed as a GET parameter
     and options ('from=' & 'to=') are query string arguments. """

    input_format, output_format = request.args.get('from', 'oldhepdata'), request.args.get('to', 'yaml')

    if input_format not in ['yaml', 'oldhepdata'] or \
            output_format not in ['root', 'yoda', 'csv', 'yaml']:
        return display_error(
            title="Chosen formats are not supported",
            description="Supported input formats: oldhepdata, yaml\n" +
                        "Supported output formats: root, yoda, csv"
        )

    fileobject = request.files.get('file')
    if not fileobject or not fileobject.filename.endswith('.zip'):
        print("Fileobject: " + str(fileobject))
        return display_error(
            title="Please send a zip file for conversion",
            description="No file has been sent or it does not have a zip extension"
        )

    filename = secure_filename(fileobject.filename)
    timestamp = str(int(round(time.time())))
    input_archive = os.path.join(current_app.config['CFG_TMPDIR'], timestamp + '.zip')
    fileobject.save(input_archive)

    options = {
        'input_format': input_format,
        'output_format': output_format,
        'filename': filename[:-4],
    }
    output_file = os.path.join(current_app.config['CFG_TMPDIR'], timestamp + '.tar.gz')
    conversion_result = convert_zip_archive(input_archive, output_file, options)

    os.remove(input_archive)

    if not conversion_result:
        return display_error(
            title="Your archive does not contain necessary files",
            description="For YAML conversions a submission.yaml file is necessary,"
                        " and for conversions from the oldhepdata format"
                        " a file with .oldhepdata extension is required."
        )

    return send_file(conversion_result, as_attachment=True)


@blueprint.route('/submission/<inspire_id>/<file_format>')
@blueprint.route('/submission/<inspire_id>/<int:version>/<file_format>')
@blueprint.route('/submission/<inspire_id>/<int:version>/<file_format>/<rivet>')
def download_submission_with_inspire_id(*args, **kwargs):
    """
       Gets the submission file and either serves it back directly from YAML, or converts it
       for other formats.

       :param inspire_id: inspire id
       :param version: version of submission to export. If absent, returns the latest.
       :param file_format: yaml, csv, root, or yoda
       :param rivet: Rivet analysis name to override default written in YODA export
       :return:
    """

    inspire_id = kwargs.pop('inspire_id')

    if 'ins' in inspire_id:
        inspire_id = inspire_id.replace('ins', '')

    submission = get_latest_hepsubmission(inspire_id=inspire_id)

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with Inspire ID {0} does not exist".format(inspire_id)
        )

    recid = submission.publication_recid
    version_count, version_count_all = get_version_count(recid)

    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    if version_count < version_count_all and version == version_count_all:
        # Check for a user trying to access a version of a publication record where they don't have permissions.
        abort(403)
    elif version < version_count_all:
        submission = HEPSubmission.query.filter_by(inspire_id=inspire_id, version=version).first()

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with Inspire ID {0} and version {1} does not exist".format(inspire_id, version)
        )

    return download_submission(submission, kwargs.pop('file_format'), rivet_analysis_name=kwargs.pop('rivet', ''))


@blueprint.route('/submission/<int:recid>/<file_format>')
@blueprint.route('/submission/<int:recid>/<int:version>/<file_format>')
@blueprint.route('/submission/<int:recid>/<int:version>/<file_format>/<rivet>')
def download_submission_with_recid(*args, **kwargs):
    """
        Gets the submission file and either serves it back directly from YAML, or converts it
        for other formats.

        :param recid: submissions recid
        :param version: version of submission to export. If absent, returns the latest.
        :param file_format: yaml, csv, root, or yoda
        :param rivet: Rivet analysis name to override default written in YODA export
        :return:
    """
    recid = kwargs.pop('recid')

    version_count, version_count_all = get_version_count(recid)
    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    # Check for a user trying to access a version of a publication record where they don't have permissions.
    if version_count < version_count_all and version == version_count_all:
        abort(403)

    submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).first()

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with record ID {0} and version {1} does not exist".format(recid, version)
        )

    return download_submission(submission, kwargs.pop('file_format'), rivet_analysis_name=kwargs.pop('rivet', ''))


@shared_task()
def download_submission(submission, file_format, offline=False, force=False, rivet_analysis_name=''):
    """
    Gets the submission file and either serves it back directly from YAML, or converts it
    for other formats.

    :param submission: HEPSubmission
    :param file_format: yaml, csv, root, or yoda
    :param offline: offline creation of the conversion when a record is finalised
    :param force: force recreation of the conversion
    :param rivet_analysis_name: Rivet analysis name to override default written in YODA export
    :return:
    """

    version = submission.version

    file_identifier = submission.publication_recid
    if submission.inspire_id:
        file_identifier = 'ins{0}'.format(submission.inspire_id)

    if file_format == 'json':
        return redirect('/record/{0}?version={1}&format=json'.format(file_identifier, version))
    elif file_format not in CFG_SUPPORTED_FORMATS:
        if offline:
            log.error('Format not supported')
        return display_error(
            title="The " + file_format + " output format is not supported",
            description="This output format is not supported. " +
                        "Currently supported formats: " + str(CFG_SUPPORTED_FORMATS),
        )

    path = os.path.join(current_app.config['CFG_DATADIR'], str(submission.publication_recid))
    data_filename = current_app.config['SUBMISSION_FILE_NAME_PATTERN'].format(submission.publication_recid, version)

    output_file = 'HEPData-{0}-v{1}-{2}.tar.gz'.format(file_identifier, submission.version, file_format)

    converted_dir = os.path.join(current_app.config['CFG_DATADIR'], 'converted')
    if not os.path.exists(converted_dir):
        os.mkdir(converted_dir)

    if file_format == 'yoda' and rivet_analysis_name:
        # Don't store in converted_dir since rivet_analysis_name might possibly change between calls.
        output_path = os.path.join(current_app.config['CFG_TMPDIR'], output_file)
    else:
        output_path = os.path.join(converted_dir, output_file)

        # If the file is already available in the dir, send it back
        # unless we are forcing recreation of the file or the submission is not finished.
        if os.path.exists(output_path) and not force and submission.overall_status == 'finished':
            if not offline:
                return send_file(output_path, as_attachment=True)
            else:
                print('File already downloaded at {0}'.format(output_path))
                return

    converter_options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'filename': 'HEPData-{0}-v{1}-{2}'.format(file_identifier, submission.version, file_format),
    }

    if submission.doi and submission.overall_status != 'sandbox':
        converter_options['hepdata_doi'] = '{0}.v{1}'.format(submission.doi, version)

    if file_format == 'yoda':
        if rivet_analysis_name:
            converter_options['rivet_analysis_name'] = rivet_analysis_name
        elif submission.inspire_id:
            record = get_record_contents(submission.publication_recid)
            if record:
                converter_options['rivet_analysis_name'] = '{0}_{1}_I{2}'.format(
                    ''.join(record['collaborations']).upper(), record['year'], submission.inspire_id)

    data_filepath = os.path.join(path, data_filename)

    converted_file = convert_zip_archive(data_filepath, output_path, converter_options)
    if not offline:
        return send_file(converted_file, as_attachment=True)
    else:
        print('File for {0} created successfully at {1}'.format(file_identifier, output_path))


@blueprint.route('/table/<inspire_id>/<path:table_name>/<file_format>')
@blueprint.route('/table/<inspire_id>/<path:table_name>/<int:version>/<file_format>')
@blueprint.route('/table/<inspire_id>/<path:table_name>/<int:version>/<file_format>/<rivet>')
def download_data_table_by_inspire_id(*args, **kwargs):
    """
    Downloads the latest data file given the url /download/submission/ins1283842/Table 1/yaml or
    by a particular version given /download/submission/ins1283842/Table 1/1/yaml

    :param args:
    :param kwargs: inspire_id, table_name, version (optional), and file_format
    :return:
    """
    inspire_id = kwargs.pop('inspire_id')
    table_name = kwargs.pop('table_name')
    rivet = kwargs.pop('rivet', '')

    if 'ins' in inspire_id:
        inspire_id = inspire_id.replace('ins', '')

    submission = get_latest_hepsubmission(inspire_id=inspire_id)

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with Inspire ID {0} does not exist".format(inspire_id)
        )

    recid = submission.publication_recid
    version_count, version_count_all = get_version_count(recid)

    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    if version_count < version_count_all and version == version_count_all:
        # Check for a user trying to access a version of a publication record where they don't have permissions.
        abort(403)

    datasubmission = None
    original_table_name = table_name
    try:
        datasubmission = DataSubmission.query.filter_by(publication_inspire_id=inspire_id, version=version, name=table_name).one()
    except NoResultFound:
        try:
            # Try again with $ signs removed from table name.
            datasubmission = DataSubmission.query.filter(
                DataSubmission.publication_inspire_id == inspire_id,
                DataSubmission.version == version,
                func.replace(DataSubmission.name, '$', '') == table_name
            ).one()
        except NoResultFound:
            if ' ' not in table_name:
                # Allow space in table_name to be omitted from URL.
                table_name = table_name.replace('Table', 'Table ')
                try:
                    datasubmission = DataSubmission.query.filter_by(publication_inspire_id=inspire_id, version=version, name=table_name).one()
                except NoResultFound:
                    pass

    if not datasubmission:
        return display_error(
            title="No data submission found",
            description="A data submission with Inspire ID {0}, version {1} and table name '{2}' does not exist"
                .format(inspire_id, version, original_table_name)
        )

    return download_datatable(datasubmission, kwargs.pop('file_format'),
                              submission_id='ins{0}'.format(inspire_id), table_name=datasubmission.name,
                              rivet_analysis_name=rivet)


@blueprint.route('/table/<int:recid>/<path:table_name>/<file_format>')
@blueprint.route('/table/<int:recid>/<path:table_name>/<int:version>/<file_format>')
@blueprint.route('/table/<int:recid>/<path:table_name>/<int:version>/<file_format>/<rivet>')
def download_data_table_by_recid(*args, **kwargs):
    """
    Record ID download
    Downloads the latest data file given the url /download/submission/1231/Table 1/yaml or
    by a particular version given /download/submission/1231/Table 1/1/yaml

    :param args:
    :param kwargs: inspire_id, table_name, version (optional), and file_format
    :return:
    """
    recid = kwargs.pop('recid')
    table_name = kwargs.pop('table_name')
    rivet = kwargs.pop('rivet', '')

    version_count, version_count_all = get_version_count(recid)
    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    # Check for a user trying to access a version of a publication record where they don't have permissions.
    if version_count < version_count_all and version == version_count_all:
        abort(403)

    datasubmission = None
    original_table_name = table_name
    try:
        datasubmission = DataSubmission.query.filter_by(publication_recid=recid, version=version, name=table_name).one()
    except NoResultFound:
        try:
            # Try again with '$' signs removed from table name.
            datasubmission = DataSubmission.query.filter(
                DataSubmission.publication_recid == recid,
                DataSubmission.version == version,
                func.replace(DataSubmission.name, '$', '') == table_name
            ).one()
        except NoResultFound:
            if ' ' not in table_name:
                # Allow space in table_name to be omitted from URL.
                table_name = table_name.replace('Table', 'Table ')
                try:
                    datasubmission = DataSubmission.query.filter_by(publication_recid=recid, version=version,name=table_name).one()
                except NoResultFound:
                    pass

    if not datasubmission:
        return display_error(
            title="No data submission found",
            description="A data submission with record ID {0}, version {1} and table name '{2}' does not exist"
                .format(recid, version, original_table_name)
        )

    return download_datatable(datasubmission, kwargs.pop('file_format'),
                              submission_id='{0}'.format(recid), table_name=datasubmission.name,
                              rivet_analysis_name=rivet)


@blueprint.route('/table/<int:data_id>/<file_format>')
def download_datatable_by_dataid(data_id, file_format):
    """ Download a particular data table in a given format. """

    datasubmission = DataSubmission.query.filter_by(id=data_id).one()

    return download_datatable(datasubmission, file_format, submission_id=data_id)


def download_datatable(datasubmission, file_format, *args, **kwargs):

    if file_format == 'json':
        return redirect('/record/data/{0}/{1}/{2}'.format(datasubmission.publication_recid,
                                                   datasubmission.id, datasubmission.version))
    elif file_format not in CFG_SUPPORTED_FORMATS:
        return display_error(
            title="The " + file_format + " output format is not supported",
            description="This output format is not supported. " +
                        "Currently supported formats: " + str(CFG_SUPPORTED_FORMATS),
        )

    dataresource = DataResource.query.filter_by(id=datasubmission.data_file).one()

    record_path, table_name = os.path.split(dataresource.file_location)

    filename = 'HEPData-{0}-v{1}'.format(kwargs.pop('submission_id'), datasubmission.version)
    if 'table_name' in kwargs:
        filename += '-' + kwargs.pop('table_name').replace(' ', '_').replace('/', '_')

    output_path = os.path.join(current_app.config['CFG_TMPDIR'], filename)

    if file_format == 'yaml':
        return send_file(
            dataresource.file_location,
            as_attachment=True,
            attachment_filename=filename + '.yaml'
        )

    options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'table': table_name,
        'filename': table_name.split('.')[0],
    }

    hepsubmission = HEPSubmission.query.filter_by(publication_recid=datasubmission.publication_recid,
                                                  version=datasubmission.version).first()

    if datasubmission.doi and hepsubmission.overall_status != 'sandbox':
        options['hepdata_doi'] = datasubmission.doi.rsplit('/', 1)[0].encode('ascii')

    if file_format == 'yoda':
        rivet_analysis_name = kwargs.pop('rivet_analysis_name', '')
        if rivet_analysis_name:
            options['rivet_analysis_name'] = rivet_analysis_name
        elif datasubmission.publication_inspire_id:
            record = get_record_contents(datasubmission.publication_recid)
            if record:
                options['rivet_analysis_name'] = '{0}_{1}_I{2}'.format(
                    ''.join(record['collaborations']).upper(), record['year'], datasubmission.publication_inspire_id)

    successful = convert(
        CFG_CONVERTER_URL,
        record_path,
        output=output_path + '-dir',
        options=options,
        extract=False,
    )

    if successful:
        new_path = output_path + "." + file_format
        new_path = extract(output_path + '-dir', new_path)
        os.remove(output_path + '-dir')
        file_to_send = get_file_in_directory(new_path, file_format)
    else:
        # Error occurred, the output is a HTML file
        file_to_send = output_path + '-dir'
        file_format = 'html'

    return send_file(file_to_send, as_attachment=True,
                     attachment_filename=filename + '.' + file_format)


def display_error(title='Unknown Error', description=''):
    return render_template(
        'hepdata_records/error_page.html',
        message=title,
        errors={
            "Converter": [{
                "level": "error",
                "message": description
            }]
        }
    )


def get_version_count(recid):
    """ Returns both the number of *allowed* versions and the number of *all* versions. """

    # Count number of all versions and number of finished versions of a publication record.
    version_count_all = HEPSubmission.query.filter_by(publication_recid=recid).count()
    version_count_finished = HEPSubmission.query.filter_by(publication_recid=recid, overall_status='finished').count()
    version_count_sandbox = HEPSubmission.query.filter_by(publication_recid=recid, overall_status='sandbox').count()

    if version_count_sandbox:
        # For a Sandbox record, there is only one version, which is accessible by everyone.
        version_count = version_count_all
    else:
        # Number of versions that a user is allowed to access based on their permissions.
        version_count = version_count_all if user_allowed_to_perform_action(recid) else version_count_finished

    return version_count, version_count_all
