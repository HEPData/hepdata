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

import socket
from datetime import datetime, timedelta
from urllib2 import HTTPError
import zipfile
from celery import shared_task
from flask import current_app
import os
import shutil
import yaml
from yaml.scanner import ScannerError

from hepdata.config import CFG_PUB_TYPE
from hepdata.ext.elasticsearch.api import get_records_matching_field, index_record_ids
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.dashboard.views import do_finalise
from hepdata.modules.records.utils.common import zipdir
from hepdata.modules.records.utils.data_processing_utils import str_presenter
from hepdata.modules.records.utils.submission import \
    process_submission_directory, get_or_create_hepsubmission, \
    remove_submission
from hepdata.modules.records.utils.workflow import create_record, update_record
import logging

__author__ = 'eamonnmaguire'

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
        print "errors"
        for file in self.errors:
            print file
            for error_message in self.errors[file]:
                print "\t{0} for {1}".format(error_message, self.record_id)


@shared_task
def update_submissions(inspire_ids_to_update, only_record_information=False):
    migrator = Migrator()
    for index, inspire_id in enumerate(inspire_ids_to_update):
        _cleaned_id = inspire_id.replace("ins", "")
        _matching_records = get_records_matching_field('inspire_id', _cleaned_id)
        if len(_matching_records['hits']['hits']) >= 1:
            print 'The record with id {} will be updated now'.format(inspire_id)
            recid = _matching_records['hits']['hits'][0]['_source']['recid']
            if 'related_publication' in _matching_records['hits']['hits'][0]['_source']:
                recid = _matching_records['hits']['hits'][0]['_source']['related_publication']
            migrator.update_file.delay(inspire_id, recid,
                                       only_record_information)
        else:
            log.error('No record exists with id {0}. You should load this file first.'.format(inspire_id))


@shared_task
def add_or_update_records_since_date(date=None):
    """
    Given a date, gets all the records updated or added since that
    date and updates or adds the corresponding records
    :param date: in the format YYYYddMM (e.g. 20160705 for the 5th July 2016)
    :return:
    """
    if not date:
        # then use yesterdays date
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y%m%d")

    inspire_ids = get_all_ids_in_current_system(date)
    print("{0} records to be added or updated since {1}.".format(len(inspire_ids), date))
    load_files(inspire_ids)


def get_all_ids_in_current_system(date=None, prepend_id_with="ins"):
    """
    Finds all the IDs that have been added or updated since some date
    :param date:
    :param prepend_id_with:
    :return:
    """
    import requests, re

    brackets_re = re.compile(r'\[+|\]+')
    inspire_ids = []
    base_url = 'http://hepdata.cedar.ac.uk/allids/{0}'
    if date:
        base_url = base_url.format(date)
    else:
        base_url = base_url.format('')

    response = requests.get(base_url)
    if response.ok:
        _all_ids = response.text
        for match in re.finditer('\[[0-9]+,[0-9]+,[0-9]+\]', _all_ids):
            start = match.start()
            end = match.end()
            # process the block which is of the form [inspire_id,xxx,xxx]
            id_block = brackets_re.sub("", _all_ids[start:end])
            id = id_block.split(',')[0].strip()
            if id != '0': inspire_ids.append(
                prepend_id_with + "{}".format(id))
    return inspire_ids


def load_files(inspire_ids, send_tweet=False, synchronous=False):
    """
    :param send_tweet: whether or not to tweet this entry.
    :param inspire_ids: array of inspire ids to load (in the format insXXX).
    :return: None
    """
    migrator = Migrator()
    from hepdata.ext.elasticsearch.api import record_exists
    for index, inspire_id in enumerate(inspire_ids):
        _cleaned_id = inspire_id.replace("ins", "")
        if not record_exists(_cleaned_id):
            print 'The record with id {} does not exist in the database, so we\'re loading it.' \
                .format(inspire_id)
            try:
                log.info('Loading {}'.format(inspire_id))
                if synchronous:
                    migrator.load_file(inspire_id, send_tweet)
                else:
                    migrator.load_file.delay(inspire_id, send_tweet)
            except socket.error as se:
                print 'socket error...'
                print se.message
            except Exception as e:
                log.error('Failed to load {0}. {1} '.format(inspire_id, e))
                print e
        else:
            print 'The record with inspire id {0} already exists. Updating instead.'.format(inspire_id)
            log.info('Updating {}'.format(inspire_id))
            if synchronous:
                update_submissions([inspire_id], send_tweet)
            else:
                update_submissions.delay([inspire_id], send_tweet)


class Migrator(object):
    """
    Performs the interface for all migration-related tasks including downloading, splitting files, YAML cleaning, and
    loading.
    """

    def __init__(self, base_url="http://hepdata.cedar.ac.uk/view/{0}/yaml"):
        self.base_url = base_url

    @shared_task
    def update_file(inspire_id, recid, only_record_information=False, send_tweet=False):
        self = Migrator()

        file_location = self.download_file(inspire_id)
        if file_location:
            updated_record_information = self.retrieve_publication_information(inspire_id)
            record_information = update_record(recid, updated_record_information)

            if not only_record_information:
                self.split_files(file_location, os.path.join(current_app.config['CFG_DATADIR'], inspire_id),
                                 os.path.join(current_app.config['CFG_DATADIR'], inspire_id + ".zip"))
                output_location = os.path.join(current_app.config['CFG_DATADIR'], inspire_id)

                try:
                    recid = self.load_submission(
                        record_information, output_location, os.path.join(output_location, "submission.yaml"),
                        update=True)

                    if recid is not None:
                        do_finalise(recid, publication_record=record_information,
                                    force_finalise=True, send_tweet=send_tweet, update=True)

                except FailedSubmission as fe:
                    log.error(fe.message)
                    fe.print_errors()
                    remove_submission(fe.record_id)
            else:
                index_record_ids([record_information['recid']])

        else:
            log.error('Failed to load {0}'.format(inspire_id))

    @shared_task
    def load_file(inspire_id, send_tweet):
        self = Migrator()
        file_location = self.download_file(inspire_id)
        if file_location:

            self.split_files(file_location, os.path.join(current_app.config['CFG_DATADIR'], inspire_id),
                             os.path.join(current_app.config['CFG_DATADIR'], inspire_id + ".zip"))

            record_information = self.retrieve_publication_information(inspire_id)
            record_information = create_record(record_information)

            output_location = os.path.join(current_app.config['CFG_DATADIR'], inspire_id)

            try:
                recid = self.load_submission(
                    record_information, output_location,
                    os.path.join(output_location, "submission.yaml"))
                if recid is not None:
                    do_finalise(recid, publication_record=record_information,
                                force_finalise=True, send_tweet=send_tweet)

            except FailedSubmission as fe:
                log.error(fe.message)
                fe.print_errors()
                remove_submission(fe.record_id)
        else:
            log.error('Failed to load ' + inspire_id)

    def download_file(self, inspire_id):
        """
        :param inspire_id:
        :return:
        """
        import urllib2
        import tempfile

        try:
            response = urllib2.urlopen(self.base_url.format(inspire_id))
            yaml = response.read()
            # save to tmp file

            tmp_file = tempfile.NamedTemporaryFile(dir=current_app.config['CFG_TMPDIR'],
                                                   delete=False)
            tmp_file.write(yaml)
            tmp_file.close()
            return tmp_file.name

        except HTTPError as e:
            log.error('Failed to download {0}'.format(inspire_id))
            log.error(e.message)
            return None

    def write_submission_yaml_block(self, document, submission_yaml,
                                    type="info"):
        submission_yaml.write("---\n")
        self.cleanup_yaml(document, type)
        yaml.add_representer(str, str_presenter)
        yaml.dump(document, submission_yaml, allow_unicode=True)
        submission_yaml.write("\n")

    def split_files(self, file_location, output_location,
                    archive_location=None):
        """
        :param file_location:
        :param output_location:
        :param archive_location:
        :return:
        """
        try:
            file_documents = yaml.safe_load_all(open(file_location, 'r'))

            # make a submission directory where all the files will be stored.
            # delete a directory in the event that it exists.
            if os.path.exists(output_location):
                shutil.rmtree(output_location)

            os.makedirs(output_location)

            with open(os.path.join(output_location, "submission.yaml"),
                      'w') as submission_yaml:
                for document in file_documents:
                    if "record_ids" in document:
                        self.write_submission_yaml_block(
                            document, submission_yaml)
                    else:
                        file_name = document["name"].replace(' ', '') + ".yaml"
                        document["data_file"] = file_name

                        with open(os.path.join(output_location, file_name),
                                  'w') as data_file:
                            yaml.add_representer(str, str_presenter)
                            yaml.dump(
                                {"independent_variables":
                                    self.cleanup_data_yaml(
                                        document["independent_variables"]),
                                    "dependent_variables":
                                        self.cleanup_data_yaml(
                                            document["dependent_variables"])},
                                data_file, allow_unicode=True)

                        self.write_submission_yaml_block(document,
                                                         submission_yaml,
                                                         type="record")

            if archive_location:
                if os.path.exists(archive_location):
                    os.remove(archive_location)

                zipf = zipfile.ZipFile(archive_location, 'w')
                os.chdir(output_location)
                zipdir(".", zipf)
                zipf.close()
        except ScannerError as se:
            current_app.logger.exception()
            current_app.logger.error(
                'Error parsing {0}, {1}'.format(file_location, se.message))

    def retrieve_publication_information(self, inspire_id):
        """
        :param inspire_id: id for record to get. If this contains
        'ins', the 'ins' is removed.
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
            print 'ERRORS ARE: '
            print errors

        if errors:
            raise FailedSubmission("Submission failed for {0}.".format(
                record_information['recid']), errors,
                record_information['recid'])
        else:
            return record_information["recid"]

    def cleanup_data_yaml(self, yaml):
        """
        Casts strings to numbers where possible, e.g
        :param yaml:
        :return:
        """
        if yaml is None:
            yaml = []

        self.convert_string_to_numbers(yaml)

        return yaml

    def convert_string_to_numbers(self, variable_set):
        fields = ["value", "high", "low"]

        if variable_set is not None:
            for variable in variable_set:
                if type(variable) is dict:
                    if variable["values"] is not None:
                        for value_item in variable["values"]:
                            try:
                                for field in fields:
                                    if field in value_item:
                                        value_item[field] = float(
                                            value_item[field])
                            except ValueError:
                                pass
                    else:
                        variable["values"] = []
        else:
            variable_set = []

    def cleanup_yaml(self, yaml, type):
        keys_to_remove = ["independent_variables",
                          "dependent_variables", "publicationyear", "preprintyear"]
        self.remove_keys(yaml, keys_to_remove)

        if type is 'info':
            self.add_field_if_needed(yaml, 'comment',
                                     'No description provided.')
        else:
            self.add_field_if_needed(yaml, 'keywords', [])
            self.add_field_if_needed(yaml, 'description',
                                     'No description provided.')

        if "label" in yaml:
            yaml["location"] = yaml["label"]
            del yaml["label"]

    def add_field_if_needed(self, yaml, field_name, default_value):
        if not (field_name in yaml):
            yaml[field_name] = default_value

    def remove_keys(self, yaml, to_remove):
        """
        :param yaml:
        :return:
        """
        for key in yaml:
            if not yaml[key]:
                to_remove.append(key)

        for key in to_remove:
            if key in yaml:
                del yaml[key]
