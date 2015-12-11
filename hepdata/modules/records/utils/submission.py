import uuid
import zipfile
from datetime import datetime
from elasticsearch import NotFoundError
from hepdata_validator.data_file_validator import DataFileValidator
from hepdata_validator.submission_file_validator import \
    SubmissionFileValidator
from invenio_ext.sqlalchemy.utils import session_manager
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
from invenio_records.models import RecordMetadata
import os
from sqlalchemy.orm.exc import NoResultFound
import yaml
from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE, CFG_DATADIR
from hepdata.ext.elasticsearch.api import get_records_matching_field, \
    delete_item_from_index
from hepdata.modules.records.models import DataSubmission, DataReview, \
    DataResource, License, Keyword, HEPSubmission, SubmissionParticipant
from hepdata.modules.records.utils.common import \
    get_prefilled_dictionary, infer_file_type, URL_PATTERNS, \
    encode_string, zipdir
from hepdata.modules.records.utils.common import get_or_create
from hepdata.modules.records.utils.resources import download_resource_file
from invenio_db import db

__author__ = 'eamonnmaguire'

SUBMISSION_FILE_NAME_PATTERN = 'HEPData-{}-v{}-yaml.zip'


def assign_record_id(record_information, id=None):
    """
    :param record_information:
    :return:
    """
    if id:
        record_information['recid'] = id
    else:
        record_id = Record.create(record_information).id
        PersistentIdentifier.create('recid', record_id,
                                          object_type='rec',
                                          object_uuid=uuid.uuid4(),
                                          status=PIDStatus.REGISTERED)

    # bit redundant, but the recid is used in many places.
    record_information['control_number'] = record_information['recid']


def remove_submission(record_id):
    """
    Removes the database entries related to a record.
    :param record_id:
    :return:
    todo: modify model so that deletes are cascaded
          through other related db entries.
    """
    hepdata_submission = HEPSubmission.query.filter_by(
        publication_recid=record_id)

    try:
        db.session.delete(hepdata_submission.one())
    except NoResultFound as nrf:
        print nrf.args

    publication_record = RecordMetadata.query.filter_by(id=record_id).first()
    if publication_record:
        data_records = get_records_matching_field(
            'related_publication', record_id, doc_type=CFG_DATA_TYPE)

        if 'hits' in data_records:
            for data_record in data_records['hits']['hits']:
                metadata_obj = RecordMetadata.query.filter_by(
                    id=data_record['_source']['recid']).one()
                db.session.delete(metadata_obj)

        submissions = DataSubmission.query.filter_by(
            publication_recid=record_id).all()

        for submission in submissions:
            DataSubmission.query.filter_by(id=submission.data_file).delete()

            for additional_resource in submission.additional_files:
                db.session.delete(additional_resource)

            DataResource.query.filter_by(id=submission.data_file).delete()

            db.session.delete(submission)

        # remove any reviews and associate review messages
        reviews = DataReview.query.filter_by(
            publication_recid=record_id).all()
        for review in reviews:
            for message in review.messages:
                db.session.delete(message)
            db.session.delete(review)

        # remove submission participant records
        SubmissionParticipant.query.filter_by(
            publication_recid=record_id).delete()

        db.session.delete(publication_record)
        db.session.commit()
        return True

    return False


@session_manager
def cleanup_submission(recid, version, to_keep):
    """
    Removes old, unreferenced files from the submission.
    This ensures that when users replace a submission,
    old files are not left behind.
    :param recid: publication recid of parent
    :param to_keep: an array of names to keep in the submission
    :return:
    """
    data_submissions = DataSubmission.query.filter_by(
        publication_recid=recid, version=version).all()

    for data_submission in data_submissions:

        if not (data_submission.name in to_keep):
            print 'Deleting Submission {0}'.format(data_submission.name)
            data_reviews = DataReview.query.filter_by(
                data_recid=data_submission.id).all()

            for review in data_reviews:
                print 'Deleting Associated Review {0}'.format(review.id)
                db.session.delete(review)

            db.session.delete(data_submission)


@session_manager
def cleanup_data_resources(data_submission):
    """
    Removes additional resources from the submission to avoid duplications.
    This ensures that when users replace a submission,
    old files are not left behind.
    :param data_submission: DataSubmission object to be cleaned
    :return:
    """
    for additional_file in data_submission.additional_files:
        db.session.delete(additional_file)


def process_data_file(basepath, data_sub, datasubmission, main_file_path):
    """
    Takes a data file and any supplementary files and persists their
    metadata to the database whilst recording their upload path.
    :param basepath:
    :param data_sub:
    :param datasubmission:
    :param main_file_path:
    :return:
    """
    main_data_file = DataResource(
        file_location=main_file_path, file_type="data")

    if "data_license" in data_sub:
        dict = get_prefilled_dictionary(
            ["name", "url", "description"], data_sub["data_license"])

        license = get_or_create(
            db.session, License, name=dict['name'],
            url=dict['url'], description=dict['description'])

        main_data_file.file_license = license.id

    db.session.add(main_data_file)
    db.session.commit()

    datasubmission.data_file = main_data_file.id

    if "location" in data_sub:
        datasubmission.location_in_publication = data_sub["location"]

    if "keywords" in data_sub:
        for keyword in data_sub["keywords"]:
            keyword_name = keyword['name']
            for value in keyword['values']:
                keyword = Keyword(name=keyword_name, value=value)
                datasubmission.keywords.append(keyword)

    cleanup_data_resources(datasubmission)

    if "additional_resources" in data_sub:
        for additional_resource in data_sub["additional_resources"]:

            if "location" in additional_resource:

                additional_resource["file_type"] = infer_file_type(
                    additional_resource["location"])
                if additional_resource["file_type"] in URL_PATTERNS:
                    # We take the file path as is,
                    # since it's a URL that we accept.
                    additional_file_path = additional_resource["location"]
                else:
                    additional_file_path = os.path.join(
                        basepath, additional_resource["location"])

                description = ""
                if "description" in additional_resource:
                    description = additional_resource["description"]

                additional_file = DataResource(
                    file_location=additional_file_path,
                    file_type=additional_resource["file_type"],
                    file_description=description)

                if "license" in additional_resource:
                    dict = get_prefilled_dictionary(
                        ["name", "url", "description"],
                        additional_resource["license"])

                    license = get_or_create(
                        db.session, License, name=dict['name'],
                        url=dict['url'], description=dict['description'])
                    additional_file.file_license = license.id

                datasubmission.additional_files.append(additional_file)

    db.session.commit()


def process_general_submission_info(submission_info_document, recid):
    """
    Processes the top level information about a submission,
    extracting the information about the data abstract,
    additional resources for the submission (files, links,
    and html inserts) and historical modification information.
    :param submission_info_document: the data document
    :param recid:
    :return:
    """
    from dateutil.parser import parse
    if 'comment' in submission_info_document \
            or 'modifications' in submission_info_document \
            or 'record_ids' in submission_info_document:

        hepsubmission = get_or_create_hepsubmission(recid)
        hepsubmission.data_abstract = encode_string(
            submission_info_document['comment'])

        if "modifications" in submission_info_document:
            for modification in submission_info_document['modifications']:
                try:
                    date = parse(modification['date'])
                except ValueError as ve:
                    date = datetime.now()

                # don't add another if it's not necessary to do so
                existing_participant = SubmissionParticipant.query.filter_by(
                    publication_recid=recid,
                    full_name=modification["who"],
                    role=modification["action"],
                    action_date=date)

                if existing_participant.count() == 0:
                    participant = SubmissionParticipant(
                        publication_recid=recid, full_name=modification["who"],
                        role=modification["action"], action_date=date)
                    db.session.add(participant)

        if 'additional_resources' in submission_info_document:
            for reference in submission_info_document['additional_resources']:

                existing_resources = DataResource.query.filter_by(
                    file_location=reference['location']).all()
                for resource in existing_resources:
                    db.session.delete(resource)
                    db.session.commit()

                resource_location = reference['location']

                file_type = 'resource'

                if '.html' in resource_location:
                    file_type = 'html'

                if 'resource' in resource_location:
                    resource_location = download_resource_file(
                        recid, resource_location)

                new_reference = DataResource(
                    file_location=resource_location, file_type=file_type,
                    file_description=reference['description'])
                hepsubmission.references.append(new_reference)

        db.session.add(hepsubmission)
        db.session.commit()


def process_submission_directory(basepath, submission_file_path, recid):
    """
    Goes through an entire submission directory and processes the
    files within to create DataSubmissions
    with the files and related material attached as DataResources.
    :param basepath:
    :param submission_file_path:
    :param recid:
    :return:
    """
    added_file_names = []
    errors = {}

    if submission_file_path is not None:
        submission_file = open(submission_file_path, 'r')

        submission_file_validator = SubmissionFileValidator()
        is_valid_submission_file = submission_file_validator.validate(
            submission_file_path)

        data_file_validator = DataFileValidator()

        if is_valid_submission_file:
            submission_processed = yaml.load_all(submission_file)
            # process file, extracting contents, and linking
            # the data record with the parent publication

            hepsubmission = get_or_create_hepsubmission(recid)

            # if it is finished and we receive an update,
            # then we need to reopen the submission to allow for revisions.
            if hepsubmission.overall_status == 'finished':
                hepsubmission.overall_status = 'todo'
                hepsubmission.latest_version += 1
                db.session.add(hepsubmission)

            for yaml_document in submission_processed:
                if 'record_ids' in yaml_document \
                        or 'comment' in yaml_document \
                        or 'modifications' in yaml_document:
                    # comments are only present in the general submission
                    # information document.
                    process_general_submission_info(yaml_document, recid)
                else:
                    existing_datasubmission_query = DataSubmission.query \
                        .filter_by(name=encode_string(yaml_document["name"]),
                                   publication_recid=recid,
                                   version=hepsubmission.latest_version)

                    added_file_names.append(yaml_document["name"])

                    if existing_datasubmission_query.count() == 0:

                        datasubmission = DataSubmission(
                            publication_recid=recid,
                            name=encode_string(yaml_document["name"]),
                            description=encode_string(
                                yaml_document["description"]),
                            version=hepsubmission.latest_version)

                    else:
                        datasubmission = existing_datasubmission_query.one()
                        datasubmission.description = encode_string(
                            yaml_document["description"])

                    db.session.add(datasubmission)

                    main_file_path = os.path.join(basepath,
                                                  yaml_document["data_file"])

                    if data_file_validator.validate(main_file_path):
                        process_data_file(basepath, yaml_document,
                                          datasubmission, main_file_path)
                    else:
                        errors = process_validation_errors_for_display(
                            data_file_validator.get_messages())

                        data_file_validator.clear_messages()

            cleanup_submission(recid, hepsubmission.latest_version,
                               added_file_names)

            db.session.commit()

            if len(errors) is 0:
                if not os.path.exists(os.path.join(CFG_DATADIR, str(recid))):
                    os.makedirs(os.path.join(CFG_DATADIR, str(recid)))

                zip_location = os.path.join(
                    CFG_DATADIR, str(recid),
                    SUBMISSION_FILE_NAME_PATTERN
                    .format(recid, hepsubmission.latest_version))
                if os.path.exists(zip_location):
                    os.remove(zip_location)

                zipf = zipfile.ZipFile(zip_location, 'w')
                os.chdir(basepath)
                zipdir(".", zipf)
                zipf.close()
        else:
            errors = process_validation_errors_for_display(
                submission_file_validator.get_messages())

            submission_file_validator.clear_messages()
            data_file_validator.clear_messages()
    else:
        # return an error
        errors = {"submission.yaml": [
            {"level": "error",
             "message": "No submission.yaml file found in submission."}
        ]}
        return errors

    # we return all the errors collectively.
    # This makes more sense that returning errors as
    # soon as problems are found on one file.
    return errors


def process_validation_errors_for_display(errors):
    processed_errors = {}

    for file in errors:
        if "/" in file:
            file_name = file.rsplit("/", 1)[1]
        else:
            file_name = file

        processed_errors[file_name] = []
        for error in errors[file]:
            processed_errors[file_name].append(
                {"level": error.level,
                 "message": error.message.encode("utf-8")
                 })

    return processed_errors


def get_or_create_hepsubmission(recid, coordinator=1, status="todo"):
    hepsubmission = HEPSubmission.query.filter_by(publication_recid=recid) \
        .first()

    if hepsubmission is None:
        hepsubmission = HEPSubmission(publication_recid=recid,
                                      coordinator=coordinator,
                                      overall_status=status)

        db.session.add(hepsubmission)
        db.session.commit()

    return hepsubmission


def create_data_review(data_recid, publication_recid, version=1):
    """
    Creates a new data review given a data record id and a pubication record id
    :param data_recid:
    :param publication_recid:
    :return:
    """

    record = get_or_create(db.session, DataReview,
                           publication_recid=publication_recid,
                           data_recid=data_recid,
                           version=version)
    return record


def unload_submission(record_id):
    print('unloading {}...'.format(record_id))
    remove_submission(record_id)

    data_records = get_records_matching_field("related_publication", record_id)
    for record in data_records["hits"]["hits"]:
        print("\t Removed data table {0} from index".format(record["_id"]))
        delete_item_from_index(doc_type=CFG_DATA_TYPE, id=record["_id"])

    try:
        delete_item_from_index(doc_type=CFG_PUB_TYPE, id=record_id)
        print("Removed publication {0} from index".format(record_id))
    except NotFoundError as nfe:
        print nfe.message

    print('Finished unloading {0}.'.format(record_id))
