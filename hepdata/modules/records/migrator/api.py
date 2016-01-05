import socket
from urllib2 import HTTPError
import zipfile
from celery import shared_task
from flask import current_app
import os
import shutil
import yaml
from yaml.scanner import ScannerError
from hepdata.config import CFG_DATADIR, CFG_TMPDIR

from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.modules.dashboard.views import do_finalise
from hepdata.modules.records.utils.common import zipdir, \
    transform_record_information_for_bibupload
from hepdata.modules.records.utils.submission import \
    process_submission_directory, get_or_create_hepsubmission, \
    remove_submission
from hepdata.modules.records.utils.workflow import create_record
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
def load_files(inspire_ids):
    """
    :param inspire_ids:
    :return:
    """
    migrator = Migrator()
    from hepdata.ext.elasticsearch.api import record_exists
    for index, inspire_id in enumerate(inspire_ids):
        _cleaned_id = inspire_id.replace("ins", "")
        if not record_exists(_cleaned_id):
            try:
                log.warn('Loading {}'.format(inspire_id))
                migrator.load_file.delay(inspire_id)
            except socket.error as se:
                print 'socket error...'
                print se.message
            except Exception as e:
                print 'Failed to load {0} :( '.format(inspire_id)
                print e
        else:
            print 'The record with id {} already exists in the database. ' \
                  'We shant be loading it again thank you very much.' \
                .format(inspire_id)


class Migrator(object):
    """
    """

    def __init__(self, base_url="http://hepdata.cedar.ac.uk/view/{0}/yaml"):
        self.base_url = base_url

    @shared_task
    def load_file(inspire_id):
        self = Migrator()

        file_location = self.download_file(inspire_id)
        if file_location:
            # create a dictionary that contains references to a submission
            # yaml, and N data files.
            self.split_files(file_location,
                             os.path.join(CFG_DATADIR, inspire_id),
                             os.path.join(CFG_DATADIR, inspire_id + ".zip"))
            record_information = self.retrieve_publication_information(
                inspire_id)

            record_information = create_record(record_information)

            output_location = os.path.join(CFG_DATADIR, inspire_id)

            try:
                recid = self.load_submission(
                    record_information, output_location,
                    os.path.join(output_location, "submission.yaml"))
                if recid is not None:

                    do_finalise(recid, publication_record=record_information,
                                force_finalise=True)

            except FailedSubmission as fe:
                # log.error(fe.message)
                # fe.print_errors()
                remove_submission(fe.record_id)
                raise
        else:
            log.error('Failed to load ' + inspire_id)

    def finalise_submissions(self, recids):

        """
        :param recids: []
        :return:
        """
        for recid in recids:
            do_finalise(recid, force_finalise=True)
            pass

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

            tmp_file = tempfile.NamedTemporaryFile(dir=CFG_TMPDIR,
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
            file_documents = yaml.load_all(open(file_location, 'r'))

            # make a submission directory where all the files will be stored.
            # delete a directory in the event that it exists.
            if os.path.exists(output_location):
                shutil.rmtree(output_location)

            os.makedirs(output_location)

            with open(os.path.join(output_location, "submission.yaml"),
                      'w') as submission_yaml:
                for document in file_documents:
                    if "record_ids" in document:
                        self.write_submission_yaml_block(document,
                                                         submission_yaml)

                    else:
                        file_name = document["name"].replace(' ', '') + ".yaml"
                        document["data_file"] = file_name

                        with open(os.path.join(output_location, file_name),
                                  'w') as data_file:
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
        return transform_record_information_for_bibupload(content)

    def load_submission(self, record_information, file_base_path,
                        submission_yaml_file_location):
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
                                              record_information["recid"])

        if len(errors) > 0:
            print 'ERRORS ARE: '
            print errors

        if errors:
            raise FailedSubmission("Submission failed for {0}.".format(
                record_information['recid']), errors,
                record_information['recid'])
        else:

            # TODO: send_email_to_coordinators_etc.
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
        keys_to_remove = ["dateupdated",
                          "independent_variables",
                          "dependent_variables"]
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
