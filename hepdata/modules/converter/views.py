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

"""HEPData Converter Views."""

import fileinput
import logging
import os
import re
import shutil
import tempfile

from flask import Blueprint, send_file, render_template, \
    current_app, redirect, abort, request
from hepdata.config import CFG_CONVERTER_URL, CFG_SUPPORTED_FORMATS, CFG_CONVERTER_TIMEOUT

from hepdata_converter_ws_client import convert, Error
from hepdata.modules.permissions.api import user_allowed_to_perform_action, verify_observer_key
from hepdata.modules.converter import convert_zip_archive
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission, DataResource, DataSubmission
from hepdata.utils.file_extractor import extract, get_file_in_directory
from hepdata.modules.records.utils.common import get_record_contents, \
    find_file_in_directory
from hepdata.modules.records.utils.data_files import get_converted_directory_path, \
    find_submission_data_file_path, get_data_path_for_record


from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, or_

from dateutil.parser import parse

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint('converter', __name__,
                      url_prefix="/download",
                      template_folder='templates',
                      static_folder='static')

FORMATS = ','.join(['json'] + CFG_SUPPORTED_FORMATS)


@blueprint.route(f'/submission/<inspire_id>/<any({FORMATS}):file_format>')
@blueprint.route(f'/submission/<inspire_id>/<int:version>/<any({FORMATS}):file_format>')
@blueprint.route('/submission/<inspire_id>/<int:version>/<any(yoda,yoda1,yoda.h5):file_format>/<rivet>')
def download_submission_with_inspire_id(*args, **kwargs):
    """
    Gets the submission file and either serves it back directly from YAML, or converts it
    for other formats.  Routes:\n
    ``/submission/<inspire_id>/<file_format>``\n
    ``/submission/<inspire_id>/<int:version>/<file_format>``\n
    ``/submission/<inspire_id>/<int:version>/<file_format>/<rivet>``

    :param inspire_id: inspire id
    :param version: version of submission to export. If absent, returns the latest.
    :param file_format: json, yaml, csv, root, yoda, yoda1, yoda.h5 or original
    :param rivet: Rivet analysis name to override default written in YODA export
    :return: download_submission
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

    return download_submission(submission, kwargs.pop('file_format'),
                               rivet_analysis_name=kwargs.pop('rivet', ''),
                               yoda_keep_qualifiers=bool(request.args.get('qualifiers', False)))


@blueprint.route(f'/submission/<int:recid>/<any({FORMATS}):file_format>')
@blueprint.route(f'/submission/<int:recid>/<int:version>/<any({FORMATS}):file_format>')
@blueprint.route('/submission/<int:recid>/<int:version>/<any(yoda,yoda1,yoda.h5):file_format>/<rivet>')
def download_submission_with_recid(*args, **kwargs):
    """
    Gets the submission file and either serves it back directly from YAML, or converts it
    for other formats.  Routes:\n
    ``/submission/<int:recid>/<file_format>``\n
    ``/submission/<int:recid>/<int:version>/<file_format>``\n
    ``/submission/<int:recid>/<int:version>/<file_format>/<rivet>``\n

    :param recid: submissions recid
    :param version: version of submission to export. If absent, returns the latest.
    :param file_format: json, yaml, csv, root, yoda, yoda1, yoda.h5 or original
    :param rivet: Rivet analysis name to override default written in YODA export
    :return: download_submission
    """
    recid = kwargs.pop('recid')
    observer_key = request.args.get('observer_key')
    key_verified = verify_observer_key(recid, observer_key)

    version_count, version_count_all = get_version_count(recid)
    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    # Check for a user trying to access a version of a publication record where they don't have permissions.
    if version_count < version_count_all and version == version_count_all and not key_verified:
        abort(403)

    submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).first()

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with record ID {0} and version {1} does not exist".format(recid, version)
        )

    return download_submission(submission, kwargs.pop('file_format'),
                               rivet_analysis_name=kwargs.pop('rivet', ''),
                               yoda_keep_qualifiers=bool(request.args.get('qualifiers', False)))


def download_submission(submission, file_format, offline=False, force=False,
                        rivet_analysis_name='', yoda_keep_qualifiers=False):
    """
    Gets the submission file and either serves it back directly from YAML, or converts it
    for other formats.

    :param submission: HEPSubmission
    :param file_format: json, yaml, csv, root, yoda, yoda1, yoda.h5 or original
    :param offline: offline creation of the conversion when a record is finalised
    :param force: force recreation of the conversion
    :param rivet_analysis_name: Rivet analysis name to override default written in YODA export
    :param yoda_keep_qualifiers: whether to keep qualifiers in YODA export
    :return: display_error or send_file depending on success of conversion
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

    data_filepath = find_submission_data_file_path(submission)

    if file_format == 'original':
        file_format_and_extension = os.path.splitext(data_filepath)[1]
    else:
        file_format_dashed = file_format.replace('.', '-')
        file_format_and_extension = '-{0}.tar.gz'.format(file_format_dashed)

    output_file = 'HEPData-{0}-v{1}{2}'.format(file_identifier, submission.version, file_format_and_extension)

    converted_dir = get_converted_directory_path(submission.publication_recid)
    if not os.path.exists(converted_dir):
        os.makedirs(converted_dir, exist_ok=True)

    if file_format.startswith('yoda') and (rivet_analysis_name or yoda_keep_qualifiers):
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

    if file_format == 'original':
        create_original_with_resources(submission, data_filepath, output_path)
        if not offline:
            return send_file(output_path, as_attachment=True)
        else:
            print('File created at {0}'.format(output_path))
            return

    file_format_dashed = file_format.replace('.', '-')
    converter_options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'filename': 'HEPData-{0}-v{1}-{2}'.format(file_identifier, submission.version, file_format_dashed),
        'validator_schema_version': '0.1.0',
    }

    if submission.doi and not submission.overall_status.startswith('sandbox'):
        converter_options['hepdata_doi'] = '{0}.v{1}'.format(submission.doi, version)

    if file_format.startswith('yoda'):
        if not rivet_analysis_name:
            rivet_analysis_name = guess_rivet_analysis_name(submission)
        if rivet_analysis_name:
            converter_options['rivet_analysis_name'] = rivet_analysis_name
        if yoda_keep_qualifiers:
            converter_options['yoda_keep_qualifiers'] = True

    try:
        converted_file = convert_zip_archive(data_filepath, output_path, converter_options)

        if not offline:
            return send_file(converted_file, as_attachment=True)
        else:
            print('File for {0} created successfully at {1}'.format(file_identifier, output_path))
    except Error as error:  # hepdata_converter_ws_client.Error
        if not offline:
            return display_error(title='Report concerns to info@hepdata.net', description=str(error))
        else:
            print('File conversion for {0} at {1} failed: {2}'.format(
                file_identifier, output_path, str(error)
            ))


@blueprint.route(f'/table/<inspire_id>/<path:table_name>/<any({FORMATS}):file_format>')
@blueprint.route(f'/table/<inspire_id>/<path:table_name>/<int:version>/<any({FORMATS}):file_format>')
@blueprint.route('/table/<inspire_id>/<path:table_name>/<int:version>/<any(yoda,yoda1,yoda.h5):file_format>/<rivet>')
def download_data_table_by_inspire_id(*args, **kwargs):
    """
    Downloads the latest data file given the url ``/download/submission/ins1283842/Table 1/yaml`` or
    by a particular version given ``/download/submission/ins1283842/Table 1/1/yaml``.  Routes:\n
    ``/table/<inspire_id>/<path:table_name>/<file_format>``\n
    ``/table/<inspire_id>/<path:table_name>/<int:version>/<file_format>``\n
    ``/table/<inspire_id>/<path:table_name>/<int:version>/<file_format>/<rivet>``\n

    :param args:
    :param kwargs: inspire_id, table_name, version (optional), and file_format
    :return: display_error or download_datatable depending on success of conversion
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
        if ' ' not in table_name:
            # Allow spaces in table_name to be omitted from URL.
            try:
                datasubmission = DataSubmission.query.filter(
                    DataSubmission.publication_inspire_id == inspire_id,
                    DataSubmission.version == version,
                    func.replace(DataSubmission.name, ' ', '') == table_name
                ).one()
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
                              rivet_analysis_name=rivet,
                              yoda_keep_qualifiers=bool(request.args.get('qualifiers', False)))


@blueprint.route(f'/table/<int:recid>/<path:table_name>/<any({FORMATS}):file_format>')
@blueprint.route(f'/table/<int:recid>/<path:table_name>/<int:version>/<any({FORMATS}):file_format>')
@blueprint.route('/table/<int:recid>/<path:table_name>/<int:version>/<any(yoda,yoda1,yoda.h5):file_format>/<rivet>')
def download_data_table_by_recid(*args, **kwargs):
    """
    Record ID download.
    Downloads the latest data file given the url ``/download/submission/1231/Table 1/yaml`` or
    by a particular version given ``/download/submission/1231/Table 1/1/yaml``.  Routes:
    ``/table/<int:recid>/<path:table_name>/<file_format>``\n
    ``/table/<int:recid>/<path:table_name>/<int:version>/<file_format>``\n
    ``/table/<int:recid>/<path:table_name>/<int:version>/<file_format>/<rivet>``\n

    :param args:
    :param kwargs: inspire_id, table_name, version (optional), and file_format
    :return: display_error or download_datatable depending on success of conversion
    """
    recid = kwargs.pop('recid')
    table_name = kwargs.pop('table_name')
    rivet = kwargs.pop('rivet', '')
    observer_key = request.args.get('observer_key')
    key_verified = verify_observer_key(recid, observer_key)

    version_count, version_count_all = get_version_count(recid)
    if 'version' in kwargs:
        version = kwargs.pop('version')
    else:
        # If version not given explicitly, take to be latest allowed version (or 1 if there are no allowed versions).
        version = version_count if version_count else 1

    # Check for a user trying to access a version of a publication record where they don't have permissions.
    if version_count < version_count_all and version == version_count_all  and not key_verified:
        abort(403)

    if not key_verified:
        observer_key = None

    datasubmission = None
    original_table_name = table_name
    try:
        datasubmission = DataSubmission.query.filter_by(publication_recid=recid, version=version, name=table_name).one()
    except NoResultFound:
        if ' ' not in table_name:
            try:
                # Allow spaces in table_name to be omitted from URL.
                datasubmission = DataSubmission.query.filter(
                    DataSubmission.publication_recid == recid,
                    DataSubmission.version == version,
                    func.replace(DataSubmission.name, ' ', '') == table_name
                ).one()
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
                              rivet_analysis_name=rivet, observer_key=observer_key,
                              yoda_keep_qualifiers=bool(request.args.get('qualifiers', False)))


@blueprint.route(f'/table/<int:data_id>/<any({FORMATS}):file_format>')
def download_datatable_by_dataid(data_id, file_format):
    """
    Download a particular data table in a given format.

    :param data_id:
    :param file_format:
    :return: download_datatable
    """
    datasubmission = DataSubmission.query.filter_by(id=data_id).one()

    return download_datatable(datasubmission, file_format, submission_id=data_id)


def download_datatable(datasubmission, file_format, *args, **kwargs):
    """
    Download a particular data table given a ``datasubmission``.

    :param datasubmission:
    :param file_format:
    :param args:
    :param kwargs:
    :return: display_error or send_file depending on success of conversion
    """

    if file_format == 'json':
        redirect_url = '/record/data/{0}/{1}/{2}'.format(datasubmission.publication_recid,
                                                   datasubmission.id, datasubmission.version)
        observer_key = kwargs.get("observer_key")
        if observer_key:
            redirect_url += f"?observer_key={observer_key}"
        return redirect(redirect_url)

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
        filename += '-' + kwargs.pop('table_name').replace(' ', '_').replace('/', '_').replace('$', '').replace('\\','')

    output_path = os.path.join(current_app.config['CFG_TMPDIR'], filename)

    if file_format == 'yaml' or file_format == 'original':
        return send_file(
            dataresource.file_location,
            as_attachment=True,
            download_name=filename + '.yaml'
        )

    options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'table': table_name,
        'filename': table_name.split('.')[0],
        'validator_schema_version': '0.1.0',
    }

    hepsubmission = HEPSubmission.query.filter_by(publication_recid=datasubmission.publication_recid,
                                                  version=datasubmission.version).first()

    if datasubmission.doi and not hepsubmission.overall_status.startswith('sandbox'):
        options['hepdata_doi'] = datasubmission.doi.rsplit('/', 1)[0]

    if file_format.startswith('yoda'):
        rivet_analysis_name = kwargs.pop('rivet_analysis_name', '')
        if not rivet_analysis_name:
            rivet_analysis_name = guess_rivet_analysis_name(hepsubmission)
        if rivet_analysis_name:
            options['rivet_analysis_name'] = rivet_analysis_name
        yoda_keep_qualifiers = kwargs.pop('yoda_keep_qualifiers', False)
        if yoda_keep_qualifiers:
            options['yoda_keep_qualifiers'] = True

    try:
        successful = convert(
            current_app.config.get('CFG_CONVERTER_URL', CFG_CONVERTER_URL),
            record_path,
            output=output_path + '-dir',
            options=options,
            extract=False,
            timeout=CFG_CONVERTER_TIMEOUT,
        )
    except Error as error:  # hepdata_converter_ws_client.Error
        return display_error(title='Report concerns to info@hepdata.net', description=str(error))

    if successful:
        new_path = output_path + "." + file_format
        new_path = extract(output_path + '-dir', new_path)
        os.remove(output_path + '-dir')
        file_format = file_format[:-1] if file_format == 'yoda1' else file_format
        file_to_send = get_file_in_directory(new_path, file_format)
    else:
        # Error occurred, the output is a HTML file
        file_to_send = output_path + '-dir'
        file_format = 'html'

    return send_file(file_to_send, as_attachment=True,
                     download_name=filename + '.' + file_format)


def display_error(title='Unknown Error', description=''):
    """
    Return an HTML page containing a description of the conversion error.

    :param title:
    :param description:
    :return: render_template
    """
    return render_template(
        'hepdata_records/error_page.html',
        header_message='Converter error encountered',
        message=title,
        errors={
            "Converter": [{
                "level": "error",
                "message": description
            }]
        }
    )


def create_original_with_resources(submission, data_filepath, output_path):
    """Copy or create 'original' zip file, i.e. yaml files with resources. If
    resources were imported from hepdata.cedar.ac.uk we create a new zip
    in a format that could be re-uploaded as a submission.

    :param type submission: HEPSubmission object
    :param type data_filepath: Path to original file
    :param type output_path: Path to output file (in converted dir)
    :return: None
    """
    resource_location = os.path.join(
        get_data_path_for_record(str(submission.publication_recid)),
        'resources'
    )
    if os.path.isdir(resource_location):
        # There is a resources directory from when this record was imported
        # from the old hepdata site. We need to create a new zip with the
        # contents of data_filepath and resources
        with tempfile.TemporaryDirectory(dir=current_app.config['CFG_TMPDIR']) as tmpdir:
            # Copy resources directory into 'contents' dir in temp directory
            contents_path = os.path.join(tmpdir, 'contents')
            shutil.copytree(resource_location, contents_path)

            # Unzip data_filepath into contents path
            shutil.unpack_archive(data_filepath, contents_path)

            # Need to go through the submission file and update the paths so
            # that all resources are at the top level. This should allow the
            # zip to be re-uploaded or imported
            submission_found = find_file_in_directory(
                contents_path,
                lambda x: x == "submission.yaml"
            )
            if submission_found:
                with fileinput.FileInput(submission_found[1], inplace=True) as file:
                    p = re.compile(r'(\s+location: )\/resource\/.*\/([^\/]+)')
                    for line in file:
                        print(p.sub(r'\g<1>\g<2>', line), end='')

            # Zip up contents dir into a new file
            base, ext = os.path.splitext(output_path)
            zip_type = 'zip' if ext == '.zip' else 'gztar'
            print("Creating archive at %s" % output_path)
            shutil.make_archive(base, zip_type, contents_path)

    else:
        shutil.copy2(data_filepath, output_path)


def get_version_count(recid):
    """
    Returns both the number of *allowed* versions and the number of *all* versions.

    :param recid:
    :return: version_count, version_count_all
    """
    # Count number of all versions and number of finished versions of a publication record.
    version_count_all = HEPSubmission.query.filter_by(publication_recid=recid).count()
    version_count_finished = HEPSubmission.query.filter_by(publication_recid=recid, overall_status='finished').count()
    version_count_sandbox = HEPSubmission.query.filter(
        HEPSubmission.publication_recid == recid,
        or_(HEPSubmission.overall_status == 'sandbox', HEPSubmission.overall_status == 'sandbox_processing')
    ).count()

    if version_count_sandbox:
        # For a Sandbox record, there is only one version, which is accessible by everyone.
        version_count = version_count_all
    else:
        # Number of versions that a user is allowed to access based on their permissions.
        version_count = version_count_all if user_allowed_to_perform_action(recid) else version_count_finished

    return version_count, version_count_all


def guess_rivet_analysis_name(submission):
    """
    Try to guess the Rivet analysis name.

    :param submission: HEPSubmission object
    :return: guessed Rivet analysis name
    """
    rivet_analysis_name = ''

    # Check if this submission has a Rivet analysis as additional resources,
    # then extract the Rivet analysis name from the URL.
    for resource in submission.resources:
        if resource.file_type == 'rivet':
            rivet_analysis_name = resource.file_location.split('/')[-1]

    if not rivet_analysis_name:
        # Otherwise guess the Rivet analysis name using the collaboration name,
        # the creation year of the INSPIRE record, and the INSPIRE ID.
        record = get_record_contents(submission.publication_recid,
                                     submission.overall_status)
        if record and 'inspire_id' in record and record['inspire_id']:
            try:
                year = parse(record['creation_date']).year
            except:
                year = record['year']  # publication year
            rivet_analysis_name = '{0}_{1}_I{2}'.format(''.join(
                record['collaborations']).upper(), year, record['inspire_id'])

    return rivet_analysis_name
