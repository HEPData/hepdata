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

import json
import logging
import zipfile
from datetime import datetime
from dateutil.parser import parse

from elasticsearch import NotFoundError, ConnectionTimeout
from flask import current_app
from flask_celeryext import create_celery_app
from flask_login import current_user
from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE
from hepdata.ext.elasticsearch.admin_view.api import AdminIndexer
from hepdata.ext.elasticsearch.api import get_records_matching_field, \
    delete_item_from_index, index_record_ids, push_data_keywords
from hepdata.modules.converter.tasks import convert_and_store
from hepdata.modules.email.api import send_finalised_email
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission, DataReview, \
    DataResource, License, Keyword, HEPSubmission, RecordVersionCommitMessage
from hepdata.modules.records.utils.common import \
    get_license, infer_file_type, encode_string, zipdir, get_record_by_id, contains_accepted_url
from hepdata.modules.records.utils.common import get_or_create
from hepdata.modules.records.utils.data_files import get_data_path_for_record, \
    cleanup_old_files, delete_all_files, delete_packaged_file
from hepdata.modules.records.utils.doi_minter import reserve_dois_for_data_submissions, reserve_doi_for_hepsubmission, \
    generate_dois_for_submission
from hepdata.modules.records.utils.resources import download_resource_file
from hepdata.modules.records.utils.validators import get_data_validator, get_submission_validator
from hepdata.utils.twitter import tweet
from invenio_db import db
from invenio_pidstore.errors import PIDDoesNotExistError
import os
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
import yaml

try:
    from yaml import CSafeLoader as Loader
except ImportError: #pragma: no cover
    from yaml import SafeLoader as Loader #pragma: no cover

def construct_yaml_str(self, node):
    # Override the default string handling function
    # to always return unicode objects
    return self.construct_scalar(node)
Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)

from urllib.error import URLError

logging.basicConfig()
log = logging.getLogger(__name__)


def remove_submission(record_id, version=1):
    """
    Removes the database entries and data files related to a record.

    :param record_id:
    :param version:
    :return: True if Successful, False if the record does not exist.
    """

    hepdata_submissions = HEPSubmission.query.filter_by(
        publication_recid=record_id, version=version).all()

    try:
        try:
            for hepdata_submission in hepdata_submissions:
                db.session.delete(hepdata_submission)
                delete_packaged_file(hepdata_submission)

        except NoResultFound as nrf:
            print(nrf.args)

        if version == 1:

            admin_idx = AdminIndexer()
            admin_idx.find_and_delete(term=record_id, fields=['recid'])

        submissions = DataSubmission.query.filter_by(
            publication_recid=record_id, version=version).all()

        reviews = DataReview.query.filter_by(
            publication_recid=record_id, version=version).all()

        for review in reviews:
            db.session.delete(review)

        for submission in submissions:

            resource = DataResource.query.filter_by(
                id=submission.data_file).first()

            db.session.delete(submission)

            if resource:
                db.session.delete(resource)

        if version == 1:

            try:
                SubmissionParticipant.query.filter_by(
                    publication_recid=record_id).delete()
            except Exception:
                print("Unable to find a submission participant for {0}".format(record_id))

            try:
                record = get_record_by_id(record_id)
                data_records = get_records_matching_field(
                    'related_publication', record_id, doc_type=CFG_DATA_TYPE)

                if 'hits' in data_records:
                    for data_record in data_records['hits']['hits']:
                        data_record_obj = get_record_by_id(data_record['_source']['recid'])
                        if data_record_obj:
                            data_record_obj.delete()

                if record:
                    record.delete()

            except PIDDoesNotExistError as e:
                print('No record entry exists for {0}. Proceeding to delete other files.'.format(record_id))

        db.session.commit()
        db.session.flush()

        if version == 1:
            delete_all_files(record_id)
        else:
            latest_submission = get_latest_hepsubmission(publication_recid=record_id)
            cleanup_old_files(latest_submission)

        return True

    except Exception as e:
        db.session.rollback()
        raise e


def cleanup_submission(recid, version, to_keep):
    """
    Removes old datasubmission records from the database.
    This ensures that when users replace a submission,
    previous records are not left behind in the database.

    :param recid: publication recid of parent
    :param version: version number of record
    :param to_keep: an array of names to keep in the submission
    :return:
    """
    data_submissions = DataSubmission.query.filter_by(
        publication_recid=recid, version=version).all()

    try:
        for data_submission in data_submissions:

            if not (data_submission.name in to_keep):
                db.session.delete(data_submission)

        db.session.commit()
    except Exception as e:
        logging.error(e)
        db.session.rollback()


def cleanup_data_resources(data_submission):
    """
    Removes additional resources for a datasubmission
    from the database to avoid duplications.
    This ensures that when users replace a submission,
    old resources are not left behind in the database.

    :param data_submission: DataSubmission object to be cleaned
    :return:
    """
    for additional_file in data_submission.resources:
        db.session.delete(additional_file)
    db.session.commit()


def cleanup_data_keywords(data_submission):
    """
    Removes keywords from the database to avoid duplications.
    This ensures that when users replace a submission,
    old keywords are not left behind in the database.

    :param data_submission: DataSubmission object to be cleaned
    :return:
    """
    for keyword in data_submission.keywords:
        db.session.delete(keyword)
    db.session.commit()


def process_data_file(recid, version, basepath, data_obj, datasubmission, main_file_path):
    """
    Takes a data file and any supplementary files and persists their
    metadata to the database whilst recording their upload path.

    :param recid: the record id
    :param version: version of the resource to be stored
    :param basepath: the path the submission has been loaded to
    :param data_obj: Object representation of loaded YAML file
    :param datasubmission: the DataSubmission object representing this file in the DB
    :param main_file_path: the data file path
    :return:
    """
    main_data_file = DataResource(
        file_location=main_file_path, file_type="data")

    if "data_license" in data_obj:

        license = get_license(data_obj["data_license"])

        main_data_file.file_license = license.id

    db.session.add(main_data_file)
    # I have to do the commit here, otherwise I have no ID to reference in the data submission table.
    db.session.commit()

    datasubmission.data_file = main_data_file.id

    if "location" in data_obj:
        datasubmission.location_in_publication = data_obj["location"]

    cleanup_data_keywords(datasubmission)

    if "keywords" in data_obj:
        for keyword in data_obj["keywords"]:
            keyword_name = keyword['name']
            for value in keyword['values']:
                keyword = Keyword(name=keyword_name, value=value)
                datasubmission.keywords.append(keyword)

    cleanup_data_resources(datasubmission)

    if "additional_resources" in data_obj:
        resources = parse_additional_resources(basepath, recid, data_obj)
        for resource in resources:
            datasubmission.resources.append(resource)

    db.session.commit()


def process_general_submission_info(basepath, submission_info_document, recid):
    """
    Processes the top level information about a submission,
    extracting the information about the data abstract,
    additional resources for the submission (files, links,
    and html inserts) and historical modification information.

    :param basepath: the path the submission has been loaded to
    :param submission_info_document: the data document
    :param recid:
    :return:
    """

    hepsubmission = get_latest_hepsubmission(publication_recid=recid)

    if "comment" in submission_info_document:
        hepsubmission.data_abstract = submission_info_document['comment']

    if "dateupdated" in submission_info_document:
        try:
            hepsubmission.last_updated = parse(submission_info_document['dateupdated'], dayfirst=True)
        except ValueError:
            hepsubmission.last_updated = datetime.utcnow()
    else:
        hepsubmission.last_updated = datetime.utcnow()

    if "modifications" in submission_info_document:
        parse_modifications(hepsubmission, recid, submission_info_document)

    if 'additional_resources' in submission_info_document:

        for reference in hepsubmission.resources:
            db.session.delete(reference)

        resources = parse_additional_resources(basepath, recid, submission_info_document)
        for resource in resources:
            hepsubmission.resources.append(resource)

    db.session.add(hepsubmission)
    db.session.commit()


def parse_additional_resources(basepath, recid, yaml_document):
    """
    Parses out the additional resource section for a full submission.

    :param basepath: the path the submission has been loaded to
    :param recid:
    :param yaml_document:
    :return:
    """
    resources = []
    for reference in yaml_document['additional_resources']:
        resource_location = reference['location']

        file_type = infer_file_type(reference["location"])
        contains_pattern, pattern = contains_accepted_url(reference['location'])
        if ('http' in resource_location and 'hepdata' not in resource_location) or contains_pattern:
            if pattern:
                file_type = pattern
            else:
                file_type = 'html'

            # in case URLs do not have http added.
            if 'http' not in resource_location:
                resource_location = "http://" + resource_location

        elif 'http' not in resource_location and 'www' not in resource_location and 'resource' not in resource_location:
            # this is a file local to the submission.
            try:
                resource_location = os.path.join(basepath, resource_location)
            except Exception as e:
                raise e
        else:
            try:
                resource_location = download_resource_file(recid, resource_location)
                print('Downloaded resource location is {0}'.format(resource_location))
            except URLError as url_error:
                log.error("Unable to download {0}. The resource is unavailable.".format(resource_location))
                resource_location = None

        if resource_location:
            new_reference = DataResource(
                file_location=resource_location, file_type=file_type,
                file_description=reference['description'])

            if "license" in reference:
                resource_license = get_license(reference["license"])
                new_reference.file_license = resource_license.id

            resources.append(new_reference)

    return resources


def parse_modifications(hepsubmission, recid, submission_info_document):
    for modification in submission_info_document['modifications']:
        try:
            date = parse(modification['date'])
        except ValueError as ve:
            date = datetime.utcnow()

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
            hepsubmission.participants.append(participant)
            db.session.add(participant)


def _read_data_file(data_file_path):
    """
    Read data file allowing for multiple attempts.
    """
    attempts = 0
    data = {}
    ex = None

    while True:
        try:
            with open(data_file_path, 'r') as data_file:
                data = yaml.load(data_file, Loader=Loader)
        except Exception as e:
            attempts += 1
            ex = e
        # allow multiple attempts to read file in case of temporary disk problems
        if (data and data is not None) or attempts > 5:
            break
    return data, ex


def process_submission_directory(basepath, submission_file_path, recid, update=False, from_oldhepdata=False):
    """
    Goes through an entire submission directory and processes the
    files within to create DataSubmissions
    with the files and related material attached as DataResources.

    :param basepath:
    :param submission_file_path:
    :param recid:
    :param update:
    :param from_oldhepdata:
    :return:
    """
    added_file_names = []
    errors = {}

    if submission_file_path is None:
        # return an error
        errors = {"submission.yaml": [
            {"level": "error", "message": "No submission.yaml file found in submission."}
        ]}
        return errors

    try:
        with open(submission_file_path, 'r') as submission_file:
            submission_processed = list(yaml.load_all(submission_file, Loader=Loader))
    except Exception as ex:
        errors = {"submission.yaml": [
            {"level": "error", "message": "There was a problem parsing the file.\n" + str(ex)}
        ]}
        return errors

    submission_file_validator = get_submission_validator()
    is_valid_submission_file = submission_file_validator.validate(
        file_path=submission_file_path,
        data=submission_processed,
    )

    if is_valid_submission_file:

        # process file, extracting contents, and linking
        # the data record with the parent publication
        hepsubmission = get_latest_hepsubmission(publication_recid=recid)

        # On a new upload, we reset the flag to notify reviewers
        hepsubmission.reviewers_notified = False

        reserve_doi_for_hepsubmission(hepsubmission, update)

        no_general_submission_info = True

        data_file_validator = get_data_validator(from_oldhepdata)

        # Delete all data records associated with this submission.
        # Fixes problems with ordering where the table names are changed between uploads.
        # See https://github.com/HEPData/hepdata/issues/112
        # Side effect that reviews will be deleted between uploads.
        cleanup_submission(recid, hepsubmission.version, added_file_names)

        for yaml_document_index, yaml_document in enumerate(submission_processed):
            if not yaml_document:
                continue

            # Check for presence of local files given as additional_resources.
            if 'additional_resources' in yaml_document:
                for resource in yaml_document['additional_resources']:
                    location = os.path.join(basepath, resource['location'])
                    if not resource['location'].startswith(('http', '/resource/')):
                        if not os.path.isfile(location):
                            errors[resource['location']] = [{"level": "error", "message":
                                "Missing 'additional_resources' file from uploaded archive."}]
                        elif '/' in resource['location']:
                            errors[resource['location']] = [{"level": "error", "message":
                                "Location of 'additional_resources' file should not contain '/'."}]

            if not yaml_document_index and 'name' not in yaml_document:

                no_general_submission_info = False
                process_general_submission_info(basepath, yaml_document, recid)

            elif not all(k in yaml_document for k in ('name', 'description', 'keywords', 'data_file')):

                errors["submission.yaml"] = [{"level": "error", "message": "YAML document with index {} ".format(
                    yaml_document_index) + "missing one or more required keys (name, description, keywords, data_file)."}]

            else:

                existing_datasubmission_query = DataSubmission.query \
                    .filter_by(name=yaml_document["name"],
                               publication_recid=recid,
                               version=hepsubmission.version)

                added_file_names.append(yaml_document["name"])

                try:
                    if existing_datasubmission_query.count() == 0:
                        datasubmission = DataSubmission(
                            publication_recid=recid,
                            name=yaml_document["name"],
                            description=yaml_document["description"],
                            version=hepsubmission.version)
                    else:
                        datasubmission = existing_datasubmission_query.one()
                        datasubmission.description = yaml_document["description"]
                    db.session.add(datasubmission)

                except SQLAlchemyError as sqlex:
                    errors[yaml_document["data_file"]] = [{"level": "error", "message": str(sqlex)}]
                    db.session.rollback()
                    continue

                main_file_path = os.path.join(basepath, yaml_document["data_file"])

                data, ex = _read_data_file(main_file_path)

                if not data or data is None or ex is not None:

                    errors[yaml_document["data_file"]] = \
                        [{"level": "error", "message": "There was a problem parsing the file.\n" + str(ex)}]

                elif '/' in yaml_document["data_file"]:

                    errors[yaml_document["data_file"]] = \
                        [{"level": "error", "message": "Name of data_file should not contain '/'.\n"}]

                else:
                    schema_type = yaml_document.get('data_schema')  # Optional
                    if data_file_validator.validate(file_path=main_file_path, file_type=schema_type, data=data):
                        try:
                            process_data_file(recid, hepsubmission.version, basepath, yaml_document,
                                          datasubmission, main_file_path)
                        except SQLAlchemyError as sqlex:
                            errors[yaml_document["data_file"]] = [{"level": "error", "message":
                                "There was a problem processing the file.\n" + str(sqlex)}]
                            db.session.rollback()
                    else:
                        errors.update(process_validation_errors_for_display(data_file_validator.get_messages()))
                        data_file_validator.clear_messages()

        if no_general_submission_info:
            hepsubmission.last_updated = datetime.utcnow()
            db.session.add(hepsubmission)
            db.session.commit()

        # The line below is commented out since it does not preserve the order of tables.
        # Delete all tables above instead: side effect of deleting reviews between uploads.
        #cleanup_submission(recid, hepsubmission.version, added_file_names)

        db.session.commit()

        if len(errors) is 0:
            errors = package_submission(basepath, recid, hepsubmission)
            reserve_dois_for_data_submissions(publication_recid=recid, version=hepsubmission.version)

            admin_indexer = AdminIndexer()
            admin_indexer.index_submission(hepsubmission)

    else:

        errors = process_validation_errors_for_display(submission_file_validator.get_messages())
        submission_file_validator.clear_messages()

    # we return all the errors collectively.
    # This makes more sense that returning errors as
    # soon as problems are found on one file.
    return errors


def package_submission(basepath, recid, hep_submission_obj):
    """
    Zips up a submission directory. This is in advance of its download
    for example by users.

    :param basepath: path of directory containing all submission files
    :param recid: the publication record ID
    :param hep_submission_obj: the HEPSubmission object representing
           the overall position
    """
    path = get_data_path_for_record(str(recid))
    if not os.path.exists(path):
        os.makedirs(path)

    version = hep_submission_obj.version
    if version == 0:
        version = 1

    zip_location = os.path.join(
        path,
        current_app.config['SUBMISSION_FILE_NAME_PATTERN']
            .format(recid, version))
    if os.path.exists(zip_location):
        os.remove(zip_location)

    zipf = zipfile.ZipFile(zip_location, 'w')
    os.chdir(basepath)
    try:
        zipdir(".", zipf)
        return {}
    except Exception as e:
        return {zip_location: [{"level": "error", "message": str(e)}]}
    finally:
        zipf.close()


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
                {"level": error.level, "message": error.message.encode("utf-8")}
            )
    return processed_errors


def get_or_create_hepsubmission(recid, coordinator=1, status="todo"):
    """
    Gets or creates a new HEPSubmission record.

    :param recid: the publication record id
    :param coordinator: the user id of the user who owns this record
    :param status: e.g. todo, finished.
    :return: the newly created HEPSubmission object
    """
    hepsubmission = HEPSubmission.query.filter_by(publication_recid=recid).first()

    if hepsubmission is None:
        hepsubmission = HEPSubmission(publication_recid=recid,
                                      coordinator=coordinator,
                                      overall_status=status)

        db.session.add(hepsubmission)
        db.session.commit()

    return hepsubmission


def create_data_review(data_recid, publication_recid, version=1):
    """
    Creates a new data review given a data record id and a publication record id.

    :param data_recid:
    :param publication_recid:
    :param version:
    :return:
    """
    submission_count = DataSubmission.query.filter_by(id=data_recid).count()
    if submission_count > 0:
        record = get_or_create(db.session, DataReview,
                               publication_recid=publication_recid,
                               data_recid=data_recid,
                               version=version)
        return record

    return None


def unload_submission(record_id, version=1):

    submission = get_latest_hepsubmission(publication_recid=record_id)

    if not submission:
        print('Record {0} not found'.format(record_id))
        return

    if version == submission.version:
        print('Unloading record {0} version {1}...'.format(record_id, version))
        remove_submission(record_id, version)
    else:
        print('Not unloading record {0} version {1} (latest version {2})...'.format(record_id, version, submission.version))
        return

    if version == 1:

        data_records = get_records_matching_field("related_publication", record_id)
        for record in data_records["hits"]["hits"]:
            print("\t Removed data table {0} from index".format(record["_id"]))
            try:
                delete_item_from_index(doc_type=CFG_DATA_TYPE, id=record["_id"], parent=record_id)
            except Exception as e:
                logging.error("Unable to remove {0} from index. {1}".format(record["_id"], e))

        try:
            delete_item_from_index(doc_type=CFG_PUB_TYPE, id=record_id)
            print("Removed publication {0} from index".format(record_id))
        except NotFoundError as nfe:
            print(nfe)

    print('Finished unloading record {0} version {1}.'.format(record_id, version))


def do_finalise(recid, publication_record=None, force_finalise=False,
                commit_message=None, send_tweet=False, update=False, convert=True):
    """
        Creates record SIP for each data record with a link to the associated
        publication.

        :param synchronous: if true then workflow execution and creation is
               waited on, then everything is indexed in one go.
               If False, object creation is asynchronous, however reindexing is not
               performed. This is only really useful for the full migration of
               content.
    """
    print('Finalising record {}'.format(recid))

    hep_submission = get_latest_hepsubmission(publication_recid=recid)

    generated_record_ids = []
    if hep_submission \
        and (force_finalise or hep_submission.coordinator == int(current_user.get_id())):

        submissions = DataSubmission.query.filter_by(
            publication_recid=recid,
            version=hep_submission.version).all()

        version = hep_submission.version

        existing_submissions = {}
        if hep_submission.version > 1 or update:
            # we need to determine which are the existing record ids.
            existing_data_records = get_records_matching_field(
                'related_publication', recid, doc_type=CFG_DATA_TYPE)

            for record in existing_data_records["hits"]["hits"]:

                if "recid" in record["_source"]:
                    existing_submissions[record["_source"]["title"]] = \
                        record["_source"]["recid"]
                    delete_item_from_index(record["_id"],
                                           doc_type=CFG_DATA_TYPE, parent=record["_source"]["related_publication"])

        current_time = "{:%Y-%m-%d %H:%M:%S}".format(datetime.utcnow())

        for submission in submissions:
            finalise_datasubmission(current_time, existing_submissions,
                                    generated_record_ids,
                                    publication_record, recid, submission,
                                    version)

        try:
            record = get_record_by_id(recid)
            # If we have a commit message, then we have a record update.
            # We will store the commit message and also update the
            # last_updated flag for the record.
            record['hepdata_doi'] = hep_submission.doi

            # The last updated date will be the current date (if record not migrated from the old site).
            if hep_submission.coordinator > 1:
                hep_submission.last_updated = datetime.utcnow()

            if commit_message:
                commit_record = RecordVersionCommitMessage(
                    recid=recid,
                    version=version,
                    message=str(commit_message))

                db.session.add(commit_record)

            record['last_updated'] = datetime.strftime(
                hep_submission.last_updated, '%Y-%m-%d %H:%M:%S')
            record['version'] = version

            record.commit()

            hep_submission.inspire_id = record['inspire_id']
            hep_submission.overall_status = "finished"
            db.session.add(hep_submission)

            db.session.commit()

            create_celery_app(current_app)

            # only mint DOIs if not testing.
            if not current_app.config.get('TESTING', False):
                generate_dois_for_submission.delay(inspire_id=hep_submission.inspire_id, version=version)
                log.info("Generated DOIs for ins{0}".format(hep_submission.inspire_id))

            # Reindex everything.
            index_record_ids([recid] + generated_record_ids)
            push_data_keywords(pub_ids=[recid])

            try:
                admin_indexer = AdminIndexer()
                admin_indexer.index_submission(hep_submission)
            except ConnectionTimeout as ct:
                log.error('Unable to add ins{0} to admin index.\n{1}'.format(hep_submission.inspire_id, ct))

            send_finalised_email(hep_submission)

            if convert:
                for file_format in ['yaml', 'csv', 'yoda', 'root']:
                    convert_and_store.delay(hep_submission.inspire_id, file_format, force=True)

            if send_tweet:
                site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
                tweet(record.get('title'), record.get('collaborations'),
                      site_url + '/record/ins{0}'.format(record.get('inspire_id')), version)

            return json.dumps({"success": True, "recid": recid,
                               "data_count": len(submissions),
                               "generated_records": generated_record_ids})

        except NoResultFound:
            print('No record found to update. Which is super strange.')

    else:
        return json.dumps(
            {"success": False, "recid": recid,
             "errors": ["You do not have permission to finalise this "
                        "submission. Only coordinators can do that."]})


def finalise_datasubmission(current_time, existing_submissions,
                            generated_record_ids, publication_record, recid,
                            submission, version):
    # we now create a 'payload' for each data submission
    # by creating a record json and uploading it via a bibupload task.
    # add in key for associated publication...
    keywords = []
    for keyword in submission.keywords:
        keywords.append({"name": keyword.name,
                         "value": keyword.value,
                         "synonyms": ""})

    # we want to retrieve back the authors of the paper
    # and assign them as authors of the data too
    if not publication_record:
        publication_record = get_record_by_id(recid)

    submission_info = {
        "title": submission.name,
        "abstract": submission.description,
        "inspire_id": publication_record['inspire_id'],
        "doi": submission.doi,
        "authors": publication_record['authors'],
        "first_author": publication_record.get('first_author', None),
        "related_publication": submission.publication_recid,
        "creation_date": publication_record["creation_date"],
        "last_updated": current_time,
        "journal_info": publication_record.get("journal_info", ""),
        "keywords": keywords,
        "version": version,
        "collaborations": publication_record.get("collaborations", []),
    }

    if submission_info["title"] in existing_submissions:
        # in the event that we're performing an update operation, we need
        # to get the data record information
        # from the index, and use the same record id. This way, we'll just
        # update the submission instead of recreating
        # a completely new record.
        recid = existing_submissions[submission_info["title"]]
        submission_info["control_number"] = submission_info["recid"] = recid

    else:
        submission_info = create_record(submission_info)
        submission_info["control_number"] = submission_info["recid"]

    submission.associated_recid = submission_info['recid']
    submission.publication_inspire_id = publication_record['inspire_id']
    generated_record_ids.append(submission_info["recid"])

    submission.version = version

    data_review = DataReview.query.filter_by(data_recid=submission.id).first()
    if data_review:
        data_review.version = version
        db.session.add(data_review)

    db.session.add(submission)
