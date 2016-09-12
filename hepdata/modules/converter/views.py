#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

import os

from flask import Blueprint, send_file, render_template, \
    request, current_app
import time
from werkzeug.utils import secure_filename
from hepdata.config import CFG_CONVERTER_URL, CFG_SUPPORTED_FORMATS

from hepdata_converter_ws_client import convert
from invenio_db import db
from hepdata.modules.converter import convert_zip_archive
from hepdata.modules.submission.models import HEPSubmission, DataResource, DataSubmission
from hepdata.modules.records.utils.submission import SUBMISSION_FILE_NAME_PATTERN
from hepdata.utils.file_extractor import extract, get_file_in_directory

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


@blueprint.route('/submission/<int:recid>/<int:version>/<string:file_format>')
def download_submission(recid, version, file_format):
    """
    Gets the submission file and either serves it back directly from YAML, or converts it
    for other formats.
    :param recid: submissions recid
    :param version: version of submission to export. If -1, returns the latest.
    :param file_format: yaml, csv, ROOT, or YODA
    :return:
    """
    submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).first()
    if file_format not in CFG_SUPPORTED_FORMATS:
        return display_error(
            title="The " + file_format + " output format is not supported",
            description="This output format is not supported. " +
                        "Currently supported formats: " + CFG_SUPPORTED_FORMATS,
        )

    if not submission:
        return display_error(
            title="No submission found",
            description="A submission with ID {0} does not exist".format(recid)
        )

    if version > submission.version or version == -1:
        version = submission.version

    path = os.path.join(current_app.config['CFG_DATADIR'], str(recid))
    data_filename = SUBMISSION_FILE_NAME_PATTERN.format(recid, version)

    # If a YAML file is requested, we just need to send this back.
    if file_format == 'yaml' and os.path.exists(os.path.join(path, data_filename)):
        return send_file(os.path.join(path, data_filename), as_attachment=True)

    output_file = str(recid) + '-' + str(version) + '-' + file_format + '.tar.gz'
    output_path = os.path.join(current_app.config['CFG_TMPDIR'], output_file)

    # If the file is already available in the tmp dir, send it back.
    if os.path.exists(output_path):
        return send_file(
            output_path,
            as_attachment=True,
        )

    converter_options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'filename': str(recid) + '-' + str(version) + '-' + file_format,
    }

    data_filepath = os.path.join(path, data_filename)

    converted_file = convert_zip_archive(data_filepath,
                                         output_path,
                                         converter_options)

    return send_file(converted_file, as_attachment=True)


@blueprint.route('/table/<int:data_id>/<string:file_format>')
def download_datatable(data_id, file_format):
    """ Download a particular data table in a given format. """
    datasub = db.session.query(DataResource) \
        .join(DataSubmission) \
        .filter(DataSubmission.id == data_id) \
        .one()

    record_path, table_name = os.path.split(datasub.file_location)

    filename = 'HEPData-Table-{0}'.format(data_id)
    output_path = os.path.join(current_app.config['CFG_TMPDIR'], filename)

    if file_format == 'yaml':
        return send_file(
            datasub.file_location,
            as_attachment=True,
        )

    options = {
        'input_format': 'yaml',
        'output_format': file_format,
        'table': table_name,
        'filename': table_name.split('.')[0],
    }

    if not os.path.exists(output_path):

        successful = convert(
            CFG_CONVERTER_URL,
            record_path,
            output=output_path + '-dir',
            options=options,
            extract=False,
        )
    else:
        successful = True

    # Error occurred, the output is a HTML file
    if successful:
        new_path = output_path + "." + file_format
        new_path = extract(filename + ".tar.gz", output_path + '-dir', new_path)
        file_to_send = get_file_in_directory(new_path, file_format)
    else:
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
