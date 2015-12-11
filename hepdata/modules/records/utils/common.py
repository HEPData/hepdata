import datetime
from invenio_pidstore.resolver import Resolver
from invenio_records.api import Record
import os
from hepdata.modules.records.models import SubmissionParticipant

__author__ = 'eamonnmaguire'

FILE_TYPES = {
    "py": "Python",
    "c": "C",
    "cpp": "C++",
    "sh": "Bash Shell",
    "pl": "Perl",
    "cs": "C# Source Code",
    "java": "Java",
    "root": "ROOT",
    "json": "JSON",
    "yaml": "YAML",
    "txt": "Text",
    "RTF": "Text",
    "xls": "Excel",
    "xlsx": "Excel",
}

URL_PATTERNS = [
    "github",
    "bitbucket",
    "hepdata",
    "hepforge",
    "sourceforge",
    "sf"
]


def contains_accepted_url(file):
    for pattern in URL_PATTERNS:
        if pattern in file:
            return True, pattern
    return False, None


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'zip', "tar", "tar.gz"}
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def infer_file_type(file):
    if "." in file:
        result, pattern = contains_accepted_url(file)
        if result:
            return pattern
        else:
            extension = file.rsplit(".", 1)[1]
            if extension in FILE_TYPES:
                return FILE_TYPES[extension]
            else:
                return extension
    else:
        return "Unknown File Type"


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
        return string.encode(type)
    except AttributeError:
        return string


def decode_string(string, type="utf-8"):
    try:
        return string.decode(type)
    except AttributeError:
        return string


def zipdir(path, ziph):
    """
    From http://stackoverflow.com/questions/1855095/how-to-create-a-zip-
    archive-of-a-directory?answertab=active#tab-top
    :param path:
    :param ziph:
    :return:
    """
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


def get_prefilled_dictionary(fields, obj):
    """
    Given a list of fields, will return a dictionary that either contains the
    field value, or an empty string
    :param fields:
    :param obj:
    :return:
    """
    dict = {}
    for field in fields:
        dict[field] = ""
        if field in obj:
            try:
                dict[field] = encode_string(obj[field])
            except AttributeError:
                dict[field] = obj[field]
    return dict


def find_file_in_directory(directory, file_predicate):
    """
    Finds a file in a directory. Useful for say when the submission.yaml file
    is not at the top level of the unzipped archive but one or more levels
    below.
    :param directory:
    :param a lambda that checks if it's the file you're looking for:
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


def truncate_string(string, words):
    all_words = string.split()
    truncated_string = ' '.join(all_words[:words])

    if len(all_words) > words:
        truncated_string += '...'
    return truncated_string


def get_record_by_id(recid):
    resolver = Resolver(pid_type='recid', object_type='rec',
                        getter=Record.get_record)
    pid, record = resolver.resolve(recid)
    return record


def transform_record_information_for_bibupload(record_information):
    """
    Converts the information from Inspire in to a suitable format
    for the workflow.
    :param record_information:
    :return:
    """
    processed_authors = []
    first_author = {}

    if "authors" in record_information and record_information["authors"]:
        for author in record_information["authors"]:
            processed_authors.append(
                {"full_name": encode_string(author["full_name"]),
                 "affiliation": encode_string(author["affiliation"])})

        first_author = None
        if processed_authors:
            first_author = processed_authors[0]
    else:
        print(
            'There is no author for {}'.format(
                record_information['inspire_id']))

    abstract = ''
    if "abstract" in record_information and record_information["abstract"]:
        abstract = record_information["abstract"]

    processed_keywords = []
    for kw in record_information["keywords"]:
        processed_keywords.append({
            "name": encode_string(kw["name"]),
            "value": encode_string(kw["value"]),
            "synonyms": encode_string(kw["synonyms"])
        })

    collaborations = []
    for c in record_information.get("collaborations", []):
        encoded = encode_string(c)
        collaborations.append(encoded)

    transformation = {
        "name": encode_string(record_information["title"][0]),
        "description": encode_string(abstract),
        "inspire_id": encode_string(record_information["inspire_id"]),
        "keywords": processed_keywords,
        "creation_date": record_information["creation_date"],
        "collaborations": collaborations,
        "journal_info": encode_string(
            record_information.get("journal_info", "")),
        "doi": encode_string(record_information["doi"]),
        "authors": processed_authors,
        "_first_author": first_author,
        "_additional_authors": [],
    }

    return transformation


def get_last_updated(recid):
    submission_participant = SubmissionParticipant.query.filter_by(
        publication_recid=recid).order_by('action_date').first()
    last_updated = None
    if submission_participant:
        last_action_date = submission_participant.action_date
        print(
            "Last action on {0} was {1}, performed by {2} on {3}".format(
                recid,
                submission_participant.role,
                submission_participant.full_name,
                submission_participant.action_date))
        if last_action_date:
            try:
                if last_action_date <= datetime.datetime.now():
                    last_updated = last_action_date.strftime("%Y-%m-%d")
            except ValueError as ve:
                print ve.args
    return last_updated
