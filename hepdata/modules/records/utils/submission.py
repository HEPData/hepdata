# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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
from __future__ import absolute_import, print_function

import logging
import uuid
import zipfile
from datetime import datetime
from urllib2 import URLError

from elasticsearch import NotFoundError
from flask import current_app
from flask.ext.login import current_user
from hepdata_validator.data_file_validator import DataFileValidator
from hepdata_validator.submission_file_validator import \
    SubmissionFileValidator
from invenio_ext.sqlalchemy.utils import session_manager
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records import Record
import os
from sqlalchemy.orm.exc import NoResultFound
import yaml
from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE
from hepdata.ext.elasticsearch.api import get_records_matching_field, \
    delete_item_from_index
from hepdata.modules.records.models import DataSubmission, DataReview, \
    DataResource, License, Keyword, HEPSubmission, SubmissionParticipant
from hepdata.modules.records.utils.common import \
    get_prefilled_dictionary, infer_file_type, encode_string, zipdir, get_record_by_id, contains_accepted_url
from hepdata.modules.records.utils.common import get_or_create
from hepdata.modules.records.utils.doi_minter import reserve_dois_for_data_submissions, reserve_doi_for_hepsubmission
from hepdata.modules.records.utils.resources import download_resource_file
from invenio_db import db
from dateutil.parser import parse

__author__ = 'eamonnmaguire'

SUBMISSION_FILE_NAME_PATTERN = 'HEPData-{}-v{}-yaml.zip'

logging.basicConfig()
log = logging.getLogger(__name__)

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
    :return: True if Successful, False if the record does not exist.
    """

    hepdata_submissions = HEPSubmission.query.filter_by(
        publication_recid=record_id).all()

    try:
        try:
            for hepdata_submission in hepdata_submissions:
                db.session.delete(hepdata_submission)
        except NoResultFound as nrf:
            print(nrf.args)

        submissions = DataSubmission.query.filter_by(
            publication_recid=record_id).all()

        reviews = DataReview.query.filter_by(
            publication_recid=record_id).all()

        for review in reviews:
            db.session.delete(review)

        for submission in submissions:

            resource = DataResource.query.filter_by(
                id=submission.data_file).first()

            db.session.delete(submission)

            if resource:
                db.session.delete(resource)

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
        return True

    except Exception as e:
        db.session.rollback()
        raise e


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
            print('Deleting Submission {0}'.format(data_submission.name))
            data_reviews = DataReview.query.filter_by(
                data_recid=data_submission.id).all()

            for review in data_reviews:
                print('Deleting Associated Review {0}'.format(review.id))
                db.session.delete(review)

            db.session.delete(data_submission)


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
        dict = get_prefilled_dictionary(
            ["name", "url", "description"], data_obj["data_license"])

        license = get_or_create(
            db.session, License, name=dict['name'],
            url=dict['url'], description=dict['description'])

        main_data_file.file_license = license.id

    db.session.add(main_data_file)
    # I have to do the commit here, otherwise I have no ID to reference in the data submission table.
    db.session.commit()

    datasubmission.data_file = main_data_file.id

    if "location" in data_obj:
        datasubmission.location_in_publication = data_obj["location"]

    if "keywords" in data_obj:
        for keyword in data_obj["keywords"]:
            keyword_name = keyword['name']
            for value in keyword['values']:
                keyword = Keyword(name=keyword_name, value=value)
                datasubmission.keywords.append(keyword)

    cleanup_data_resources(datasubmission)

    if "additional_resources" in data_obj:
        resources = parse_additional_resources(basepath, recid, version, data_obj)
        for resource in resources:
            datasubmission.additional_files.append(resource)

    db.session.commit()


def process_general_submission_info(basepath, submission_info_document, recid):
    """
    Processes the top level information about a submission,
    extracting the information about the data abstract,
    additional resources for the submission (files, links,
    and html inserts) and historical modification information.
    :param submission_info_document: the data document
    :param recid:
    :return:
    """

    if 'comment' in submission_info_document \
        or 'modifications' in submission_info_document \
        or 'record_ids' in submission_info_document:

        hepsubmission = get_latest_hepsubmission(recid)
        hepsubmission.data_abstract = encode_string(
            submission_info_document['comment'])

        if "dateupdated" in submission_info_document:
            try:
                hepsubmission.last_updated = parse(submission_info_document['dateupdated'], dayfirst=True)
            except ValueError as ve:
                hepsubmission.last_updated = datetime.now()

        if "modifications" in submission_info_document:
            parse_modifications(recid, submission_info_document)

        if 'additional_resources' in submission_info_document:

            for reference in hepsubmission.references:
                db.session.delete(reference)

            resources = parse_additional_resources(basepath,
                                                   recid, hepsubmission.version, submission_info_document)
            for resource in resources:
                hepsubmission.references.append(resource)

        if hepsubmission.last_updated is not None:
            print('hepsubmission.last_updated = {}'.format(hepsubmission.last_updated.isoformat(' ')))
        db.session.add(hepsubmission)
        db.session.commit()


def parse_additional_resources(basepath, recid, version, yaml_document):
    """
    Parses out the additional resource section for a full submission
    :param hepsubmission:
    :param recid:
    :param submission_info_document:
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
                dict = get_prefilled_dictionary(
                    ["name", "url", "description"],
                    reference["license"])

                resource_license = get_or_create(
                    db.session, License, name=dict['name'],
                    url=dict['url'], description=dict['description'])
                new_reference.file_license = resource_license.id

            resources.append(new_reference)

    return resources


def parse_modifications(recid, submission_info_document):
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


def process_submission_directory(basepath, submission_file_path, recid, update=False):
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
            file_path=submission_file_path)

        data_file_validator = DataFileValidator()

        if is_valid_submission_file:
            try:
                submission_processed = yaml.load_all(submission_file, Loader=yaml.CSafeLoader)
            except:
                submission_processed = yaml.safe_load_all(submission_file)

            # process file, extracting contents, and linking
            # the data record with the parent publication
            hepsubmission = get_latest_hepsubmission(recid)
            if hepsubmission is None:
                HEPSubmission(publication_recid=recid,
                              overall_status='todo',
                              coordinator=int(current_user.get_id()),
                              version=hepsubmission.version + 1)

            # On a new upload, we reset the flag to notify reviewers
            hepsubmission.reviewers_notified = False

            # if it is finished and we receive an update,
            # then we need to reopen the submission to allow for revisions.
            if hepsubmission.overall_status == 'finished' and not update:
                # we create a new HEPSubmission object
                _rev_hepsubmission = HEPSubmission(publication_recid=recid,
                                                   overall_status='todo',
                                                   coordinator=hepsubmission.coordinator,
                                                   version=hepsubmission.version + 1)
                db.session.add(_rev_hepsubmission)
                hepsubmission = _rev_hepsubmission

            reserve_doi_for_hepsubmission(hepsubmission)

            for yaml_document in submission_processed:
                if 'record_ids' in yaml_document or 'comment' in yaml_document or 'modifications' in yaml_document:
                    # comments are only present in the general submission
                    # information document.
                    process_general_submission_info(basepath, yaml_document, recid)
                else:
                    existing_datasubmission_query = DataSubmission.query \
                        .filter_by(name=encode_string(yaml_document["name"]),
                                   publication_recid=recid,
                                   version=hepsubmission.version)

                    added_file_names.append(yaml_document["name"])

                    if existing_datasubmission_query.count() == 0:
                        datasubmission = DataSubmission(
                            publication_recid=recid,
                            name=encode_string(yaml_document["name"]),
                            description=encode_string(
                                yaml_document["description"]),
                            version=hepsubmission.version)

                    else:
                        datasubmission = existing_datasubmission_query.one()
                        datasubmission.description = encode_string(
                            yaml_document["description"])

                    db.session.add(datasubmission)

                    main_file_path = os.path.join(basepath,
                                                  yaml_document["data_file"])

                    if data_file_validator.validate(file_path=main_file_path):
                        process_data_file(recid, hepsubmission.version, basepath, yaml_document,
                                          datasubmission, main_file_path)
                    else:
                        errors = process_validation_errors_for_display(
                            data_file_validator.get_messages())

                        data_file_validator.clear_messages()

            cleanup_submission(recid, hepsubmission.version,
                               added_file_names)

            db.session.commit()

            if len(errors) is 0:
                package_submission(basepath, recid, hepsubmission)
                reserve_dois_for_data_submissions(recid, hepsubmission.version)
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


def package_submission(basepath, recid, hep_submission_obj):
    """
    Zips up a submission directory. This is in advance of its download
    for example by users
    :param basepath: path of directory containing all submission files
    :param recid: the publication record ID
    :param hep_submission_obj: the HEPSubmission object representing
           the overall position
    """
    if not os.path.exists(os.path.join(current_app.config['CFG_DATADIR'], str(recid))):
        os.makedirs(os.path.join(current_app.config['CFG_DATADIR'], str(recid)))

    version = hep_submission_obj.version
    if version == 0:
        version = 1

    zip_location = os.path.join(
        current_app.config['CFG_DATADIR'], str(recid),
        SUBMISSION_FILE_NAME_PATTERN
            .format(recid, version))
    if os.path.exists(zip_location):
        os.remove(zip_location)

    zipf = zipfile.ZipFile(zip_location, 'w')
    os.chdir(basepath)
    zipdir(".", zipf)
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
    Gets of creates a new HEPSubmission record
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


def get_latest_hepsubmission(recid):
    """
    Gets of creates a new HEPSubmission record
    :param recid: the publication record id
    :param coordinator: the user id of the user who owns this record
    :param status: e.g. todo, finished.
    :return: the newly created HEPSubmission object
    """
    hepsubmissions = HEPSubmission.query.filter_by(publication_recid=recid).all()

    last = None
    for hepsubmission in hepsubmissions:
        if last is None:
            last = hepsubmission
        else:
            if hepsubmission.version > last.version:
                last = hepsubmission

    return last


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
        try:
            delete_item_from_index(doc_type=CFG_DATA_TYPE, id=record["_id"], parent=record_id)
        except Exception as e:
            logging.error("Unable to remove {0} from index. {1}".format(record["_id"], e))

    try:
        delete_item_from_index(doc_type=CFG_PUB_TYPE, id=record_id)
        print("Removed publication {0} from index".format(record_id))
    except NotFoundError as nfe:
        print(nfe.message)

    print('Finished unloading {0}.'.format(record_id))
