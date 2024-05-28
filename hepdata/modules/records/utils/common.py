# -*- coding: utf-8 -*-
#
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
import yaml
from yaml import CBaseLoader as Loader
from invenio_db import db
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.resolver import Resolver
from invenio_records.api import Record
import os
from sqlalchemy.orm.exc import NoResultFound

from hepdata.config import HISTFACTORY_FILE_TYPE, SIZE_LOAD_CHECK_THRESHOLD
from hepdata.ext.opensearch.api import get_record
from hepdata.modules.submission.models import HEPSubmission, License, DataSubmission, DataResource

FILE_TYPES = {
    "py": "Python",
    "c": "C",
    "cpp": "C++",
    "cxx": "C++",
    "cc": "C++",
    "C": "C++",
    "sh": "Bash Shell",
    "pl": "Perl",
    "cs": "C# Source Code",
    "java": "Java",
    "root": "ROOT",
    "json": "JSON",
    "yaml": "YAML",
    "txt": "Text",
    "rtf": "Text",
    "xls": "Excel",
    "xlsx": "Excel",
    "slha": "SUSY Les Houches Accord",
    "f": "Fortran"
}

IMAGE_TYPES = [
    "png",
    "jpeg",
    "jpg",
    "tiff",
    "gif"
]

URL_PATTERNS = [
    "github",
    "bitbucket",
    "rivet",
    "zenodo",
    "sourceforge",
]

ALLOWED_EXTENSIONS = ('.zip', '.tar', '.tar.gz', '.tgz', '.oldhepdata', '.yaml', '.yaml.gz')

HISTFACTORY_EXTENSIONS = ALLOWED_EXTENSIONS[:4] + ('.tar.xz', '.json')
HISTFACTORY_TERMS = ("histfactory", "pyhf", "likelihoods", "workspaces")


def contains_accepted_url(file):
    for pattern in URL_PATTERNS:
        if pattern in file:
            return True, pattern
    return False, None


def allowed_file(filename):
    return filename.endswith(ALLOWED_EXTENSIONS)


def is_image(filename):
    if '.' in filename:
        extension = filename.rsplit(".", 1)[1]
        return extension.lower() in IMAGE_TYPES
    return False


def is_histfactory(filename, description, type=None):
    if type and type.lower() == HISTFACTORY_FILE_TYPE.lower():
        return True

    if filename.endswith(HISTFACTORY_EXTENSIONS):
        description_lc = description.lower()
        for term in HISTFACTORY_TERMS:
            if term in description_lc:
                return True

    return False


def infer_file_type(file, description, type=None):
    if "." in file:
        result, pattern = contains_accepted_url(file)
        if result:
            return pattern
        else:
            if is_histfactory(file, description, type):
                return HISTFACTORY_FILE_TYPE
            extension = file.rsplit(".", 1)[1]
            if extension in FILE_TYPES:
                return FILE_TYPES[extension]
            else:
                return extension
    else:
        return "resource"


def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance


def remove_file_extension(filename):
    if "." in filename:
        return filename.rsplit('.', 1)[0]
    else:
        return filename


def encode_string(string, type="utf-8"):
    try:
        return string.encode(type, errors='replace')
    except AttributeError:
        return string


def decode_string(string, type="utf-8"):
    try:
        return string.decode(type, errors='replace')
    except AttributeError:
        return string
    except UnicodeEncodeError:
        return string


def get_license(license_obj):
    dict = {}
    for field in ["name", "url", "description"]:
        dict[field] = ""
        if field in license_obj:
            dict[field] = license_obj[field]

    return get_or_create(
        db.session, License, name=dict['name'],
        url=dict['url'], description=dict['description'])


def find_file_in_directory(directory, file_predicate):
    """
    Finds a file in a directory. Useful for say when the submission.yaml file
    is not at the top level of the unzipped archive but one or more levels
    below.

    :param directory:
    :param file_predicate: a lambda that checks if it's the file you're looking for
    :return:
    """
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if file_predicate(filename):
                return root, os.path.join(root, filename)
    return None


def default_time(obj):
    """Default JSON serializer."""
    import datetime

    fmt = '%Y-%m-%d %H:%M:%S %Z'
    if isinstance(obj, datetime.datetime):
        return obj.strftime(fmt)
    return obj


def truncate_string(string, max_words=None, max_chars=None):
    if max_words:
        all_words = string.split()
        truncated_string = ' '.join(all_words[:max_words])

        if len(all_words) > max_words:
            truncated_string += '...'
        return truncated_string

    elif max_chars:
        if len(string) < max_chars:
            return string
        else:
            return string[:(max_chars - 3)] + '...'


def get_record_contents(recid, status=None):
    """
    Tries to get record from OpenSearch first. Failing that, it tries from the database.

    :param recid: Record ID to get.
    :param status: Status of submission. If provided and not 'finished', will not check opensearch first.
    :return: a dictionary containing the record contents if the recid exists, None otherwise.
    """
    record = None

    if status is None or status == 'finished':
        record = get_record(recid)

    if record is None:
        try:
            record = get_record_by_id(recid)
        except PIDDoesNotExistError:
            return None

    return record


def get_record_by_id(recid):
    try:
        resolver = Resolver(pid_type='recid', object_type='rec', getter=Record.get_record)
        pid, record = resolver.resolve(recid)
        return record
    except NoResultFound:
        print('No record found for recid {}'.format(recid))
        return None
    except PIDDoesNotExistError:
        print('The PID {0} does not exist'.format(recid))
        return None


def record_exists(*args, **kwargs):
    count = HEPSubmission.query.filter_by(**kwargs).count()
    return count > 0


def load_table_data(recid, version):
    """
    Loads a specfic data file's yaml file data.

    :param recid: The recid used for the query
    :param version: The data version to select
    :return table_contents: A dict containing the table data
    """

    datasub_query = DataSubmission.query.filter_by(id=recid, version=version)
    table_contents = {}
    if datasub_query.count() > 0:
        datasub_record = datasub_query.one()
        data_query = db.session.query(DataResource).filter(
            DataResource.id == datasub_record.data_file)

        if data_query.count() > 0:
            data_record = data_query.one()
            file_location = data_record.file_location

            attempts = 0
            while True:
                try:
                    with open(file_location, 'r') as table_file:
                        table_contents = yaml.load(table_file, Loader=Loader)
                except (FileNotFoundError, PermissionError) as e:
                    attempts += 1
                # allow multiple attempts to read file in case of temporary disk problems
                if (table_contents and table_contents is not None) or attempts > 5:
                    break

    return table_contents


def file_size_check(file_location, load_all):
    """
    Decides if a file breaks the maximum size threshold
        for immediate loading on the records page.

    :param file_location: Location of the data file on disk
    :param load_all: If the check should be run
    :return bool: Pass or fail
    """
    size = os.path.getsize(file_location)
    status = True if load_all == 1 else size <= SIZE_LOAD_CHECK_THRESHOLD
    return { "size": size, "status": status}


def generate_license_data_by_id(license_id):
    """
    Generates a dictionary from a License class selected by
    its ID from the database or returns the default CC0 licence information.

    :param license_id:
    :return dict: Returns the license_data dictionary
    """
    license_data = License.query.filter_by(id=license_id).first()
    if license_data:
        # Generate and return the dictionary
        return {
            "name": license_data.name,
            "url": license_data.url,
            "description": license_data.description
        }
    else:
        # If none, we return the default CC0 licence data
        return {
            "name": "CC0",
            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "description": ("CC0 enables reusers to distribute, remix, "
                            "adapt, and build upon the material in any "
                            "medium or format, with no conditions.")
        }
