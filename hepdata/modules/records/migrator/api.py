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

from __future__ import absolute_import, print_function
import socket
from datetime import datetime, timedelta
from urllib2 import HTTPError

import requests
from celery import shared_task
from flask import current_app
import os

from invenio_db import db

from hepdata.ext.elasticsearch.api import get_records_matching_field, index_record_ids
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.dashboard.views import do_finalise
from hepdata.modules.records.utils.common import record_exists

from hepdata.modules.records.utils.submission import \
    process_submission_directory, get_or_create_hepsubmission, \
    remove_submission
from hepdata.modules.records.utils.workflow import create_record, update_record
import logging

from hepdata.modules.records.utils.yaml_utils import split_files
from hepdata.modules.submission.api import get_latest_hepsubmission, is_resource_added_to_submission
from hepdata.modules.submission.models import DataResource, HEPSubmission
from hepdata.utils.file_extractor import get_file_in_directory


logging.basicConfig()
log = logging.getLogger(__name__)


class FailedSubmission(Exception):
    def __init__(self, message, errors, record_id):

        # Call the base class constructor with the parameters it needs
        super(FailedSubmission, self).__init__(message)

        # Now for your custom code...
        self.errors = errors
        self.record_id = record_id

    def print_errors(self):
        for file in self.errors:
            print(file)
            for error_message in self.errors[file]:
                print("\t{0} for {1}".format(error_message, self.record_id))


@shared_task
def update_analyses():
    endpoints = current_app.config["ANALYSES_ENDPOINTS"]
    for analysis_endpoint in endpoints:

        if "endpoint_url" in endpoints[analysis_endpoint]:

            log.info("Updating analyses from {0}...".format(analysis_endpoint))

            response = requests.get(endpoints[analysis_endpoint]["endpoint_url"])

            if response:

                analyses = response.json()

                for record in analyses:
                    submission = get_latest_hepsubmission(inspire_id=record, overall_status='finished')

                    if submission:
                        for analysis in analyses[record]:
                            _resource_url = endpoints[analysis_endpoint]["url_template"].format(analysis)
                            if not is_resource_added_to_submission(submission.publication_recid, submission.version,
                                                                   _resource_url):
                                print('Adding {} analysis to ins{} with URL {}'
                                      .format(analysis_endpoint, record, _resource_url))
                                new_resource = DataResource(
                                    file_location=_resource_url,
                                    file_type=analysis_endpoint)

                                submission.resources.append(new_resource)

                        try:
                            db.session.add(submission)
                            db.session.commit()
                            index_record_ids([submission.publication_recid])
                        except Exception as e:
                            db.session.rollback()
                            log.error(e)
                    else:
                        log.debug("An analysis is available in {0} but with no equivalent in HEPData (ins{1}).".format(
                            analysis_endpoint, record))
        else:
            log.debug("No endpoint url configured for {0}".format(analysis_endpoint))


@shared_task
def update_submissions(inspire_ids_to_update, force=False, only_record_information=False):
    migrator = Migrator()
    for index, inspire_id in enumerate(inspire_ids_to_update):
        _cleaned_id = inspire_id.replace("ins", "")
        _matching_records = get_records_matching_field("inspire_id", _cleaned_id)
        if len(_matching_records["hits"]["hits"]) >= 1:
            recid = _matching_records["hits"]["hits"][0]["_source"]["recid"]
            if "related_publication" in _matching_records["hits"]["hits"][0]["_source"]:
                recid = _matching_records["hits"]["hits"][0]["_source"]["related_publication"]
            print("The record with inspire_id {} and recid {} will be updated now".format(inspire_id, recid))
            migrator.update_file.delay(inspire_id, recid, force, only_record_information)
        else:
            log.error("No record exists with id {0}. You should load this file first.".format(inspire_id))


@shared_task
def add_or_update_records_since_date(date=None, send_tweet=False, convert=False):
    """
    Given a date, gets all the records updated or added since that
    date and updates or adds the corresponding records
    :param date: in the format YYYYddMM (e.g. 20160705 for the 5th July 2016)
    :param send_tweet
    :param convert
    :return:
    """
    if not date:
        # then use yesterdays date
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y%m%d")

    inspire_ids = get_all_ids_in_current_system(date)
    print("{0} records to be added or updated since {1}.".format(len(inspire_ids), date))
    load_files(inspire_ids, send_tweet=send_tweet, convert=convert)


def get_all_ids_in_current_system(date=None, prepend_id_with="ins"):
    """
    Finds all the IDs that have been added or updated since some date
    :param date:
    :param prepend_id_with:
    :return:
    """
    import requests, re

    brackets_re = re.compile(r"\[+|\]+")
    inspire_ids = []
    base_url = "http://hepdata.cedar.ac.uk/allids/{0}"
    if date:
        base_url = base_url.format(date)
    else:
        base_url = base_url.format("")

    response = requests.get(base_url)
    if response.ok:
        _all_ids = response.text
        for match in re.finditer("\[[0-9]+,[0-9]+,[0-9]+\]", _all_ids):
            start = match.start()
            end = match.end()
            # process the block which is of the form [inspire_id,xxx,xxx]
            id_block = brackets_re.sub("", _all_ids[start:end])
            id = id_block.split(",")[0].strip()
            if id != "0":
                inspire_ids.append("{0}{1}".format(prepend_id_with, id))
    return inspire_ids


def load_files(inspire_ids, send_tweet=False, synchronous=False, convert=False,
               base_url='http://hepdata.cedar.ac.uk/view/{0}/yaml'):
    """
    :param base_url: override default base URL
    :param convert:
    :param synchronous: if should be run immediately
    :param send_tweet: whether or not to tweet this entry.
    :param inspire_ids: array of inspire ids to load (in the format insXXX).
    :return: None
    """
    migrator = Migrator()

    for index, inspire_id in enumerate(inspire_ids):
        _cleaned_id = inspire_id.replace("ins", "")
        if not record_exists(inspire_id=_cleaned_id):
            print("The record with id {0} does not exist in the database, so we're loading it.".format(inspire_id))
            try:
                log.info("Loading {0}".format(inspire_id))
                if synchronous:
                    migrator.load_file(inspire_id, send_tweet, convert=convert, base_url=base_url)
                else:
                    migrator.load_file.delay(inspire_id, send_tweet, convert=convert, base_url=base_url)
            except socket.error as se:
                print("socket error...")
                log.error(se.message)
            except Exception as e:
                print("Failed to load {0}. {1} ".format(inspire_id, e))
                log.error("Failed to load {0}. {1} ".format(inspire_id, e))
        else:
            print("The record with inspire id {0} already exists. Updating instead.".format(inspire_id))
            log.info("Updating {}".format(inspire_id))
            if synchronous:
                update_submissions([inspire_id])
            else:
                update_submissions.delay([inspire_id])


class Migrator(object):
    """
    Performs the interface for all migration-related tasks including downloading, splitting files, YAML cleaning, and
    loading.
    """

    def __init__(self, base_url="http://hepdata.cedar.ac.uk/view/{0}/yaml"):
        self.base_url = base_url

    def prepare_files_for_submission(self, inspire_id, force_retrieval=False):
        """
        Either returns a file if it already exists, or downloads it and
        splits it.
        :param inspire_id:
        :return: output location if succesful, None if not
        """
        output_location = os.path.join(current_app.config["CFG_DATADIR"], inspire_id)
        last_updated = datetime.now()

        download = not os.path.exists(output_location) or (get_file_in_directory(output_location, 'yaml') is None)

        if download or force_retrieval:
            print("Downloading file for {0}".format(inspire_id))
            file_location = self.download_file(inspire_id)

            if file_location:
                output_location = os.path.join(current_app.config["CFG_DATADIR"], inspire_id)
                error, last_updated = split_files(file_location, output_location, "{0}.zip".format(output_location))

                # remove temporary download file after processing
                try:
                    os.remove(file_location)
                except:
                    log.info('Unable to remove {0}'.format(file_location))
            else:
                output_location = None
        else:
            print("File for {0} already in system...no download required.".format(inspire_id))

        return output_location, last_updated

    @shared_task
    def update_file(inspire_id, recid, force=False, only_record_information=False, send_tweet=False, convert=False):
        self = Migrator()

        output_location, oldsite_last_updated = self.prepare_files_for_submission(inspire_id, force_retrieval=True)
        if output_location:
            updated_record_information = self.retrieve_publication_information(inspire_id)
            record_information = update_record(recid, updated_record_information)

            hep_submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
            version_count = HEPSubmission.query.filter_by(publication_recid=recid).count()
            print('Old site last updated {}'.format(str(oldsite_last_updated)))
            print('New site last updated {}'.format(str(hep_submission.last_updated)))
            print('Coordinator ID is {}, version count is {}'.format(hep_submission.coordinator, version_count))
            allow_update = hep_submission.last_updated < oldsite_last_updated and \
                           hep_submission.coordinator == 1 and version_count == 1

            if not only_record_information and (allow_update or force):
                try:
                    recid = self.load_submission(
                        record_information, output_location, os.path.join(output_location, "submission.yaml"),
                        update=True)
                    print('Loaded record {}'.format(recid))

                    if recid is not None:
                        do_finalise(recid, publication_record=record_information,
                                    force_finalise=True, send_tweet=send_tweet, update=True, convert=convert)

                except FailedSubmission as fe:
                    log.error(fe.message)
                    fe.print_errors()
                    remove_submission(fe.record_id)
            elif not only_record_information:
                print('Not updating record {}'.format(recid))
            else:
                index_record_ids([record_information["recid"]])

        else:
            log.error("Failed to load {0}".format(inspire_id))

    @shared_task
    def load_file(inspire_id, send_tweet=False, convert=False, base_url='http://hepdata.cedar.ac.uk/view/{0}/yaml'):
        self = Migrator(base_url)
        output_location, oldsite_last_updated = self.prepare_files_for_submission(inspire_id)
        if output_location:

            record_information = create_record(self.retrieve_publication_information(inspire_id))

            try:
                recid = self.load_submission(
                    record_information, output_location,
                    os.path.join(output_location, "submission.yaml"))
                if recid is not None:
                    do_finalise(recid, publication_record=record_information,
                                force_finalise=True, send_tweet=send_tweet, convert=convert)
                    return True

            except FailedSubmission as fe:
                log.error(fe.message)
                fe.print_errors()
                remove_submission(fe.record_id)
                return False
        else:
            log.error("Failed to load " + inspire_id)
            return False

    def download_file(self, inspire_id):
        """
        :param inspire_id:
        :return:
        """
        import requests
        import tempfile
        from shutil import copyfile

        # Check if single YAML file exists in static directory.
        base_dir = os.path.dirname(os.path.realpath(__file__))
        yaml_file = os.path.join(base_dir, 'static', inspire_id + '.yaml')
        if os.path.isfile(yaml_file):
            print("Found {}".format(yaml_file))
            tmp_file = tempfile.NamedTemporaryFile(dir=current_app.config["CFG_TMPDIR"], delete=False)
            tmp_file.close()
            copyfile(yaml_file, tmp_file.name)
            return tmp_file.name

        try:
            url = self.base_url.format(inspire_id)
            log.info("Trying URL " + url)
            response = requests.get(url)
            if response.ok:
                yaml = response.text
                # save to tmp file

                tmp_file = tempfile.NamedTemporaryFile(dir=current_app.config["CFG_TMPDIR"],
                                                       delete=False)
                tmp_file.write(yaml)
                tmp_file.close()
                return tmp_file.name
            else:
                log.error('Non OK response from endpoint at {0}'.format(url))
                return None

        except HTTPError as e:
            log.error("Failed to download {0}".format(inspire_id))
            log.error(e.message)
            return None

    def retrieve_publication_information(self, inspire_id):
        """
        :param inspire_id: id for record to get. If this contains
        "ins", the "ins" is removed.
        :return: dict containing keys for:
            title
            doi
            authors
            abstract
            arxiv_id
            collaboration
        """
        if "ins" in inspire_id:
            inspire_id = int(inspire_id.replace("ins", ""))

        content, status = get_inspire_record_information(inspire_id)

        content["inspire_id"] = inspire_id
        return content

    def load_submission(self, record_information, file_base_path,
                        submission_yaml_file_location, update=False):
        """
        :param record_information:
        :param file_base_path:
        :param files:
        :return:
        """
        # create publication record.
        # load data tables
        # create data table records (call finalise(recid))
        admin_user_id = 1

        # consume data payload and store in db.

        get_or_create_hepsubmission(record_information["recid"], admin_user_id)
        errors = process_submission_directory(file_base_path,
                                              submission_yaml_file_location,
                                              record_information["recid"], update=update)

        if len(errors) > 0:
            print("ERRORS ARE: ")
            print(errors)

        if errors:
            raise FailedSubmission("Submission failed for {0}.".format(
                record_information["recid"]), errors,
                record_information["recid"])
        else:
            return record_information["recid"]
