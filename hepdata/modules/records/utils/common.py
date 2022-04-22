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
from invenio_db import db
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.resolver import Resolver
from invenio_records.api import Record
import os
from sqlalchemy.orm.exc import NoResultFound

from hepdata.config import CFG_PUB_TYPE, HISTFACTORY_FILE_TYPE
from hepdata.ext.elasticsearch.api import get_record
from hepdata.modules.submission.models import HEPSubmission, License

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

HISTFACTORY_EXTENSIONS = ALLOWED_EXTENSIONS[:4]
HISTFACTORY_TERMS = ("histfactory json", "pyhf", "likelihoods")


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
    Tries to get record from Elasticsearch first. Failing that, it tries from the database.

    :param recid: Record ID to get.
    :param status: Status of submission. If provided and not 'finished', will not check elasticsearch first.
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
