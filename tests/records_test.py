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

"""HEPData records test cases."""
import random
from io import open, StringIO
import os
import re
import requests
from time import sleep
import yaml
import shutil
import tempfile
import datetime

from flask import current_app
from flask_login import login_user
from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy.exc import MultipleResultsFound
import pytest
from werkzeug.datastructures import FileStorage
import requests_mock
import jsonschema

from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.api import process_payload, process_zip_archive, \
    move_files, get_all_ids, has_upload_permissions, \
    has_coordinator_permissions, create_new_version, \
    get_resource_mimetype, create_breadcrumb_text, format_submission, \
    format_resource, get_commit_message, get_related_to_this_hepsubmissions, \
    get_related_hepsubmissions, get_related_datasubmissions, get_related_to_this_datasubmissions
from hepdata.modules.records.importer.api import import_records
from hepdata.modules.records.utils.analyses import update_analyses, update_analyses_single_tool
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission, process_submission_directory, \
    do_finalise, unload_submission
from hepdata.modules.records.utils.common import get_record_by_id, get_record_contents, generate_license_data_by_id
from hepdata.modules.records.utils.data_processing_utils import generate_table_headers, generate_table_data
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.json_ld import get_json_ld
from hepdata.modules.records.utils.users import get_coordinators_in_system, has_role
from hepdata.modules.records.utils.workflow import update_record, create_record
from hepdata.modules.records.views import set_data_review_status
from hepdata.modules.submission.models import HEPSubmission, DataReview, \
    DataSubmission, DataResource, License, RecordVersionCommitMessage, RelatedRecid, RelatedTable
from hepdata.modules.submission.views import process_submission_payload
from hepdata.modules.submission.api import get_latest_hepsubmission
from tests.conftest import TEST_EMAIL
from hepdata.modules.records.utils.records_update_utils import get_inspire_records_updated_since, \
    get_inspire_records_updated_on, update_record_info, RECORDS_PER_PAGE
from hepdata.modules.inspire_api.views import get_inspire_record_information
from hepdata.config import CFG_TMPDIR
from hepdata.modules.records.subscribers.api import is_current_user_subscribed_to_record


def test_record_creation(app):
    """___test_record_creation___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        assert (record_information['recid'])
        assert (record_information['uuid'])
        assert (record_information['title'] == 'My Journal Paper')


def test_record_update(app):
    """___test_record_update___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        record = get_record_by_id(record_information['recid'])
        assert (record['title'] == 'My Journal Paper')
        assert (record['journal_info'] == 'Phys. Letts')
        update_record(record_information['recid'], {'journal_info': 'test'})

        updated_record = get_record_by_id(record_information['recid'])
        assert (updated_record['journal_info'] == 'test')


def test_get_record(app, client):
    with app.app_context():
        content = client.get('/record/1')
        assert (content is not None)


def test_get_record_contents(app, load_default_data, identifiers):
    # Status finished - should use OS to get results
    record1 = get_record_contents(1, status='finished')
    for key in ["inspire_id", "title"]:
        assert (record1[key] == identifiers[0][key])

    # Status todo - should use DB for result
    record2 = get_record_contents(1, status='todo')
    # DB returns data from an Invenio RecordMetadata obj so has fewer fields
    # than the OS dict
    for key in record2.keys():
        if key == 'last_updated':
            # Date format is slightly different for DB vs ES
            assert(record2[key].replace(' ', 'T') == record1[key])
        else:
            assert(record2[key] == record1[key])

    record3 = get_record_contents(1)
    assert (record3 == record1)

    assert(get_record_contents(9999999) is None)


def test_get_coordinators(app):
    with app.app_context():
        coordinators = get_coordinators_in_system()
        assert (len(coordinators) == 1)


def test_has_role(app):
    with app.app_context():
        user = User.query.filter_by(email=TEST_EMAIL).first()
        assert (user is not None)
        assert (has_role(user, 'coordinator'))
        assert (not has_role(user, 'awesome'))


def test_data_processing(app):
    base_dir = os.path.dirname(os.path.realpath(__file__))

    data = yaml.load(open(os.path.join(base_dir, 'test_data/data_table.yaml'), 'rt'), Loader=yaml.CSafeLoader)

    assert ('independent_variables' in data)
    assert ('dependent_variables' in data)

    assert (len(data['independent_variables']) == 1)
    assert (len(data['independent_variables'][0]['values']) == 3)

    assert (len(data['dependent_variables']) == 1)
    assert (len(data['dependent_variables'][0]['values']) == 3)

    data["name"] = 'test'
    data["title"] = 'test'
    data["keywords"] = None
    data["doi"] = 'doi/10.2342'
    data["related_tables"] = []
    data["related_to_this"] = []
    data["table_license"] = []
    data["location"] = 'Data from Figure 2 of preprint'
    data["review"] = []
    data["associated_files"] = []
    data["size"] = 0
    data["size_check"] = True

    table_structure = generate_table_data(data)

    assert(table_structure["x_count"] == 1)
    assert(len(table_structure["headers"]) == 2)
    assert(len(table_structure["qualifiers"]) == 2)


def test_upload_valid_file(app):
    # Test uploading and processing a file for a record
    with app.app_context():
        base_dir = os.path.dirname(os.path.realpath(__file__))

        for i, status in enumerate(["todo", "sandbox"]):
            user = User.query.first()
            login_user(user)

            recid = f'12345{i}'
            get_or_create_hepsubmission(recid, 1, status=status)

            hepdata_submission = HEPSubmission.query.filter_by(
                publication_recid=recid).first()
            assert(hepdata_submission is not None)
            assert(hepdata_submission.data_abstract is None)
            assert(hepdata_submission.created < hepdata_submission.last_updated)
            assert(hepdata_submission.version == 1)
            assert(hepdata_submission.overall_status == status)

            with open(os.path.join(base_dir, 'test_data/TestHEPSubmission.zip'), "rb") as stream:
                test_file = FileStorage(
                    stream=stream,
                    filename="TestHEPSubmission.zip"
                )
                response = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

            assert(response.json == {'url': '/test_redirect_url'})

            # Check the submission has been updated
            hepdata_submission = HEPSubmission.query.filter_by(
                publication_recid=recid).first()
            assert(hepdata_submission.data_abstract.startswith('CERN-LHC.  Measurements of the cross section  for ZZ production'))
            assert(hepdata_submission.created < hepdata_submission.last_updated)
            assert(hepdata_submission.version == 1)
            assert(hepdata_submission.overall_status == status)

            # Set the status to finished and try again, to check versioning
            if status == "todo":
                hepdata_submission.overall_status = 'finished'
                db.session.add(hepdata_submission)

            # Sleep before uploading new version to avoid dir name conflict
            sleep(1)

            # Refresh user
            user = User.query.first()
            login_user(user)

            # Upload a new version
            with open(os.path.join(base_dir, 'test_data/TestHEPSubmission.zip'), "rb") as stream:
                test_file = FileStorage(
                    stream=stream,
                    filename="TestHEPSubmission.zip"
                )
                process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

            # Check the submission has been updated (overridden for a sandbox;
            # new version for normal submission)
            expected_versions = 2 if status == "todo" else 1
            hepdata_submissions = HEPSubmission.query.filter_by(
                publication_recid=recid).order_by(HEPSubmission.last_updated).all()
            assert(len(hepdata_submissions) == expected_versions)
            assert(hepdata_submissions[0].version == 1)

            if status == "todo":
                assert(hepdata_submissions[0].overall_status == 'finished')

            assert(hepdata_submissions[-1].data_abstract.startswith('CERN-LHC.  Measurements of the cross section  for ZZ production'))
            assert(hepdata_submissions[-1].version == expected_versions)
            assert(hepdata_submissions[-1].overall_status == status)

            # Check that there are the expected number of subdirectories and
            # zip files under the record's main path
            # For status = 'todo' (standard submission) there will be 1 file
            # and 1 dir for each of 2 versions; for the sandbox submission
            # there will just be 1 file and 1 dir.
            directory = get_data_path_for_record(hepdata_submission.publication_recid)
            assert(os.path.exists(directory))
            filepaths = os.listdir(directory)
            assert(len(filepaths) == 2*expected_versions)

            dir_count = 0
            file_count = 0
            for path in filepaths:
                if os.path.isdir(os.path.join(directory, path)):
                    dir_count += 1
                    assert(re.match(r"\d{10}", path) is not None)
                else:
                    file_count += 1
                    assert(re.match(r"HEPData-%s-v[12]-yaml.zip" % recid, path) is not None)

            assert(dir_count == expected_versions)
            assert(file_count == expected_versions)

            if status == "todo":
                # Delete the v2 submission and check db and v2 files have been removed
                unload_submission(hepdata_submission.publication_recid, version=2)

                hepdata_submissions = HEPSubmission.query.filter_by(
                    publication_recid=recid).order_by(HEPSubmission.last_updated).all()
                assert(len(hepdata_submissions) == 1)
                assert(hepdata_submissions[0].version == 1)
                assert(hepdata_submissions[0].overall_status == 'finished')

                filepaths = os.listdir(directory)
                assert(len(filepaths) == 2)
                assert(f"HEPData-12345{i}-v1-yaml.zip" in filepaths)

            # Delete the submission and check everything has been removed
            unload_submission(hepdata_submission.publication_recid, version=1)

            hepdata_submissions = HEPSubmission.query.filter_by(
                publication_recid=recid).order_by(HEPSubmission.last_updated).all()
            assert(len(hepdata_submissions) == 0)

            assert(not os.path.exists(directory))


def test_upload_valid_file_yaml_gz(app):
    # Test uploading and processing a file for a record
    with app.app_context():
        base_dir = os.path.dirname(os.path.realpath(__file__))
        user = User.query.first()
        login_user(user)

        recid = '1512299'
        get_or_create_hepsubmission(recid, 1)

        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission is not None)
        assert(hepdata_submission.data_abstract is None)
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        with open(os.path.join(base_dir, 'test_data/1512299.yaml.gz'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="1512299.yaml.gz"
            )
            response = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(response.json == {'url': '/test_redirect_url'})

        # Check the submission has been updated
        hepdata_submission = HEPSubmission.query.filter_by(
            publication_recid=recid).first()
        assert(hepdata_submission.data_abstract.startswith('Unfolded differential decay rates of four kinematic variables'))
        assert(hepdata_submission.created < hepdata_submission.last_updated)
        assert(hepdata_submission.version == 1)
        assert(hepdata_submission.overall_status == 'todo')

        # Set the status to finished and try again, to check versioning
        hepdata_submission.overall_status = 'finished'
        db.session.add(hepdata_submission)

        # Refresh user
        user = User.query.first()
        login_user(user)

        with open(os.path.join(base_dir, 'test_data/1512299.yaml.gz'), "rb") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="1512299.yaml.gz"
            )
            process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        # Check the submission has been updated
        hepdata_submissions = HEPSubmission.query.filter_by(
            publication_recid=recid).order_by(HEPSubmission.last_updated).all()
        assert(len(hepdata_submissions) == 2)
        assert(hepdata_submissions[0].version == 1)
        assert(hepdata_submissions[0].overall_status == 'finished')
        assert(hepdata_submissions[1].data_abstract.startswith('Unfolded differential decay rates of four kinematic variables'))
        assert(hepdata_submissions[1].version == 2)
        assert(hepdata_submissions[1].overall_status == 'todo')


def test_upload_invalid_file(app):
    # Test uploading an invalid file
    with app.app_context():
        user = User.query.first()
        login_user(user)

        recid = '12345'
        get_or_create_hepsubmission(recid, 1)

        with StringIO("test") as stream:
            test_file = FileStorage(
                stream=stream,
                filename="test.txt"
            )
            response, code = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(code == 400)
        assert(response.json == {
            'message': 'You must upload a .zip, .tar, .tar.gz or .tgz file'
            ' (or a .oldhepdata or single .yaml or .yaml.gz file).'
        })


def test_upload_max_size(app):
    # Test uploading a file with size greater than UPLOAD_MAX_SIZE
    app.config.update({'UPLOAD_MAX_SIZE': 1000000})
    with app.app_context():
        user = User.query.first()
        login_user(user)

        recid = '12345'
        get_or_create_hepsubmission(recid, 1)

        base_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(base_dir, 'test_data/TestHEPSubmission.zip'), "rb") as stream:
            test_file = FileStorage(stream=stream, filename="TestHEPSubmission.zip")
            response, code = process_payload(recid, test_file, '/test_redirect_url', synchronous=True)

        assert(code == 413)
        pattern = re.compile(r"TestHEPSubmission\.zip too large \((\d+) bytes > (\d+) bytes\)")
        assert pattern.match(response.json['message'])


def test_has_upload_permissions(app):
    # Test uploader permissions
    with app.app_context():
        # Create a record
        recid = '12345'
        get_or_create_hepsubmission(recid, 1)

        # Check admin user has upload permissions to new record
        admin_user = user = User.query.first()
        assert has_upload_permissions(recid, admin_user)

        # Create a user who is not admin and not associated with a record
        user = User(email='testuser@hepdata.com', password='hello', active=True)
        db.session.add(user)
        db.session.commit()
        login_user(user)

        assert not has_upload_permissions(recid, user)

        # Add the user as an uploader but not primary - should not be allowed
        submission_participant = SubmissionParticipant(
            user_account=user.id, publication_recid=recid,
            email=user.email, role='uploader')
        db.session.add(submission_participant)
        db.session.commit()

        assert not has_upload_permissions(recid, user)

        # Make the participant primary uploader - should now work
        submission_participant.status = 'primary'
        db.session.add(submission_participant)
        db.session.commit()

        assert has_upload_permissions(recid, user)


def test_has_coordinator_permissions(app):
    # Test coordinator permissions
    with app.app_context():
        recid = '12345'
        hepsubmission = get_or_create_hepsubmission(recid, 1)

        # Check admin user has coordinator permissions to new record
        admin_user = user = User.query.first()
        assert has_coordinator_permissions(recid, admin_user)

        # Create a user who is not admin and not associated with a record
        user = User(email='testuser@hepdata.com', password='hello', active=True)
        db.session.add(user)
        db.session.commit()
        login_user(user)

        assert not has_coordinator_permissions(recid, user)

        # Add the user as an uploader - should not have permission
        submission_participant = SubmissionParticipant(
            user_account=user.id, publication_recid=recid,
            email=user.email, role='uploader')
        db.session.add(submission_participant)
        db.session.commit()

        assert not has_coordinator_permissions(recid, user)

        # Modify record to add this user as coordinator - should now work
        hepsubmission.coordinator = user.get_id()
        db.session.add(hepsubmission)
        db.session.commit()

        assert has_coordinator_permissions(recid, user)


def test_process_zip_archive_invalid(app):
    # Test uploading a zip containing broken symlinks
    base_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(base_dir, 'test_data/submission_invalid_symlink.tgz')
    tmp_path = tempfile.mkdtemp(dir=CFG_TMPDIR)
    shutil.copy2(file_path, tmp_path)
    tmp_file_path = os.path.join(tmp_path, 'submission_invalid_symlink.tgz')
    errors = process_zip_archive(tmp_file_path, 1)
    assert("Exceptions when copying files" in errors)
    assert(len(errors["Exceptions when copying files"]) == 1)
    assert(errors["Exceptions when copying files"][0].get("level") == "error")
    assert(errors["Exceptions when copying files"][0].get("message")
           == "Invalid file TestHEPSubmissionInvalidSymlink/invalid_file_name.txt: "
           "[Errno 2] No such file or directory: "
           "'TestHEPSubmissionInvalidSymlink/invalid_file_name.txt'"
           )
    shutil.rmtree(tmp_path)

    # Test uploading an invalid tarfile (real example: user ran 'tar -czvf' then 'gzip')
    file_path = os.path.join(base_dir, 'test_data/submission_invalid_tarfile.tgz.gz')
    tmp_path = tempfile.mkdtemp(dir=CFG_TMPDIR)
    shutil.copy2(file_path, tmp_path)
    tmp_file_path = os.path.join(tmp_path, 'submission_invalid_tarfile.tgz.gz')
    errors = process_zip_archive(tmp_file_path, 1)
    assert ("Archive file extractor" in errors)
    assert (len(errors["Archive file extractor"]) == 1)
    assert (errors["Archive file extractor"][0].get("level") == "error")
    assert (errors["Archive file extractor"][0].get("message")
            == "submission_invalid_tarfile.tgz.gz is not a valid zip or tar archive file.")
    shutil.rmtree(tmp_path)

    # Try again, using the path that we've just deleted, to simulate a disk error
    with pytest.raises(ValueError) as exc_info:
        process_zip_archive(tmp_file_path, 1)

    assert str(exc_info.value) == 'Unable to extract file submission_invalid_tarfile.tgz.gz. Please check the file is a valid zip or tar archive file and try again later. Contact info@hepdata.net if problems persist.'

    # Test uploading a file that is not in any of the given formats
    file_path = os.path.join(base_dir, 'test_data/notazip.yaml.gz')
    tmp_path = tempfile.mkdtemp(dir=CFG_TMPDIR)
    shutil.copy2(file_path, tmp_path)
    tmp_file_path = os.path.join(tmp_path, 'notazip.yaml.gz')
    errors = process_zip_archive(tmp_file_path, 1)
    assert ("Archive file extractor" in errors)
    assert (len(errors["Archive file extractor"]) == 1)
    assert (errors["Archive file extractor"][0].get("level") == "error")
    assert (errors["Archive file extractor"][0].get("message")
            == "notazip.yaml.gz is not a valid .gz file.")
    shutil.rmtree(tmp_path)

    # Test uploading an invalid yaml file
    file_path = os.path.join(base_dir, 'test_data/invalid_parser_file.yaml')
    tmp_path = tempfile.mkdtemp(dir=CFG_TMPDIR)
    shutil.copy2(file_path, tmp_path)
    tmp_file_path = os.path.join(tmp_path, 'invalid_parser_file.yaml')
    errors = process_zip_archive(tmp_file_path, 1)
    assert ("Single YAML file splitter" in errors)
    assert (len(errors["Single YAML file splitter"]) == 1)
    assert (errors["Single YAML file splitter"][0].get("level") == "error")
    assert ("did not find expected ',' or '}'" in errors["Single YAML file splitter"][0].get("message"))
    shutil.rmtree(tmp_path)

    # Try again, using the path that we've just deleted, to simulate a disk error
    with pytest.raises(ValueError) as exc_info:
        process_zip_archive(tmp_file_path, 1)

    assert str(exc_info.value) == 'Unable to extract YAML from file invalid_parser_file.yaml. Please check the file is valid YAML and try again later. Contact info@hepdata.net if problems persist.'


def test_move_files_invalid_path():
    errors = move_files('this_is_not_a_real_path', tempfile.mkdtemp(dir=CFG_TMPDIR))
    assert("Exceptions when copying files" in errors)
    assert(len(errors["Exceptions when copying files"]) == 1)
    assert(errors["Exceptions when copying files"][0].get("level") == "error")
    assert(errors["Exceptions when copying files"][0].get("message")
           == "[Errno 2] No such file or directory: 'this_is_not_a_real_path'"
           )


def test_get_updated_records_since_date(app):
    ids_since = get_inspire_records_updated_since(3)
    ids_on = get_inspire_records_updated_on(0)
    ids_on += get_inspire_records_updated_on(1)
    ids_on += get_inspire_records_updated_on(2)
    ids_on += get_inspire_records_updated_on(3)
    if ids_since == get_inspire_records_updated_since(3):  # check no further updates
        assert set(ids_on) == set(ids_since)


def test_get_updated_records_on_date(app):
    test_date = '2021-06-29'
    mock_url = 'https://inspirehep.net/api/literature?sort=mostrecent'
    mock_url += '&size={0}&page=1&fields=control_number'.format(RECORDS_PER_PAGE)
    mock_url += '&q=external_system_identifiers.schema%3AHEPData%20and%20du%3A{}'.format(test_date)
    mock_json = {'hits': {'total': 2, 'hits': [{'id': '1234567'}, {'id': '890123'}]}}
    # Use requests_mock to mock the response from inspirehep.net.
    with requests_mock.Mocker(real_http=True) as mock:
        mock.get(mock_url, json=mock_json, complete_qs=True)
        ids = get_inspire_records_updated_on(test_date)
    assert ids == ['1234567', '890123']


def test_update_record_info(app):
    """Test update of publication information from INSPIRE."""
    assert update_record_info(None) == 'Inspire ID is None'  # case where Inspire ID is None
    for inspire_id in ('1311487', '19999999'):  # check both a valid and invalid Inspire ID
        assert update_record_info(inspire_id) == 'No HEPData submission'  # before creation of HEPSubmission object
        submission = process_submission_payload(
            inspire_id=inspire_id, submitter_id=1,
            reviewer={'name': 'Reviewer', 'email': 'reviewer@hepdata.net'},
            uploader={'name': 'Uploader', 'email': 'uploader@hepdata.net'},
            send_upload_email=False
        )

        # Process the files to create DataSubmission tables in the DB.
        base_dir = os.path.dirname(os.path.realpath(__file__))
        directory = os.path.join(base_dir, 'test_data/test_submission')
        tmp_path = os.path.join(tempfile.mkdtemp(dir=CFG_TMPDIR), 'test_submission')
        shutil.copytree(directory, tmp_path)
        process_submission_directory(tmp_path, os.path.join(tmp_path, 'submission.yaml'),
                                     submission.publication_recid)
        do_finalise(submission.publication_recid, force_finalise=True, convert=False)

        if inspire_id == '19999999':
            assert update_record_info(inspire_id) == 'Invalid Inspire ID'
        else:

            # First change the publication information to that of a different record.
            different_inspire_record_information, status = get_inspire_record_information('1650066')
            assert status == 'success'
            hep_submission = get_latest_hepsubmission(inspire_id=inspire_id)
            assert hep_submission is not None
            update_record(hep_submission.publication_recid, different_inspire_record_information)

            # Then can check that the update works and that a further update is not required.
            assert update_record_info(inspire_id, send_email=True) == 'Success'
            assert update_record_info(inspire_id) == 'No update needed'  # check case where information already current

        unload_submission(submission.publication_recid)


def test_set_review_status(app, load_default_data):
    """Test we can set review status on one or all data records"""
    # Set the status of a default record to "todo" so we can modify table
    # review status
    hepsubmission = get_latest_hepsubmission(publication_recid=1)
    hepsubmission.overall_status = "todo"
    db.session.add(hepsubmission)
    db.session.commit()

    data_reviews = DataReview.query.filter_by(publication_recid=1).all()
    assert(len(data_reviews) == 0)

    # Get data records
    data_submissions = DataSubmission.query.filter_by(
        publication_recid=hepsubmission.publication_recid).order_by(
        DataSubmission.id.asc()).all()
    assert(len(data_submissions) == 14)

    # Log in
    user = User.query.first()

    # Try setting a single data submission to "attention"
    params = {
        'publication_recid': 1,
        'status': 'attention',
        'version': 1,
        'data_recid': data_submissions[1].id
    }

    with app.test_request_context('/data/review/status/', data=params):
        login_user(user)
        result = set_data_review_status()
        assert(result.json == {'recid': 1,
                               'data_id': data_submissions[1].id,
                               'status': 'attention'})
        data_reviews = DataReview.query.filter_by(publication_recid=1).all()
        assert(len(data_reviews) == 1)
        assert(data_reviews[0].publication_recid == 1)
        assert(data_reviews[0].data_recid == data_submissions[1].id)
        assert(data_reviews[0].status == 'attention')

    # Now try setting all data submissions to "passed"
    params = {
        'publication_recid': 1,
        'status': 'passed',
        'version': 1,
        'all_tables': True
    }

    with app.test_request_context('/data/review/status/', data=params):
        login_user(user)
        result = set_data_review_status()
        assert(result.json == {'recid': 1, 'success': True})
        data_reviews = DataReview.query.filter_by(publication_recid=1) \
            .order_by(DataReview.data_recid.asc()).all()
        assert(len(data_reviews) == 14)
        for i, data_review in enumerate(data_reviews):
            assert(data_review.publication_recid == 1)
            assert(data_review.data_recid == data_submissions[i].id)
            assert(data_review.status == 'passed')


def test_get_all_ids(app, load_default_data, identifiers):
    expected_record_ids = [1, 16, 57]
    # Pre-sorted based on the last_updated (today, 2016-07-13 and 2013-12-17)
    sorted_expected_record_ids = [57, 1, 16]
    sorted_expected_inspire_ids = [2751932, 1283842, 1245023]
    # Order is not guaranteed unless we use latest_first,
    # so sort the results before checking
    assert(get_all_ids() == expected_record_ids)

    # Check id_field works
    assert(get_all_ids(id_field='recid') == expected_record_ids)
    assert(get_all_ids(id_field='inspire_id')
           == [int(x["inspire_id"]) for x in identifiers])
    with pytest.raises(ValueError):
        get_all_ids(id_field='authors')

    # Check last_updated works
    # Default records were last updated on 2016-07-13 and 2013-12-17
    date_2013_1 = datetime.datetime(year=2013, month=12, day=16)
    assert(sorted(get_all_ids(last_updated=date_2013_1)) == expected_record_ids)
    date_2013_2 = datetime.datetime(year=2013, month=12, day=17)
    assert(sorted(get_all_ids(last_updated=date_2013_2)) == expected_record_ids)
    date_2013_3 = datetime.datetime(year=2013, month=12, day=18)
    assert(get_all_ids(last_updated=date_2013_3) == [1, 57])

    # A date very far away
    date_2120 = datetime.datetime(year=2120, month=1, day=1)
    assert(get_all_ids(last_updated=date_2120) == [])

    # Check sort by latest works
    assert(get_all_ids(latest_first=True) == sorted_expected_record_ids)
    assert(get_all_ids(id_field='inspire_id', latest_first=True) == sorted_expected_inspire_ids)


def test_create_new_version(app, load_default_data, identifiers, mocker):
    hepsubmission = get_latest_hepsubmission(publication_recid=1)
    assert hepsubmission.version == 1

    # Add an uploader
    uploader = SubmissionParticipant(
        publication_recid=1,
        email='test@hepdata.net',
        role='uploader',
        status='primary')
    db.session.add(uploader)
    db.session.commit()

    user = User.query.first()

    # Mock `send_cookie_email` method
    send_cookie_mock = mocker.patch('hepdata.modules.records.api.send_cookie_email')

    # Create new version of valid finished record
    result = create_new_version(1, user, uploader_message="Hello!")
    assert result.status_code == 200
    assert result.json == {'success': True, 'version': 2}

    # get_latest_hepsubmission should now return version 2
    hepsubmission = get_latest_hepsubmission(publication_recid=1)
    assert hepsubmission.version == 2
    assert hepsubmission.overall_status == 'todo'

    # Should have attempted to send uploader email
    send_cookie_mock.assert_called_with(
        uploader,
        get_record_by_id(1),
        message="Hello!",
        version=2
    )

    # Try creating a new version - should not work as status of most recent is 'todo'
    result, status_code = create_new_version(1, user)
    assert status_code == 400
    assert result.json == {
        'message': 'Rec id 1 is not finished so cannot create a new version'
    }


def test_get_resource_mimetype(app):
    # Test a file where python can detect the mimetype
    resource = DataResource(file_location='a/b/test.zip')
    assert get_resource_mimetype(resource, 'Binary') == 'application/zip'

    # Test a file for which python cannot detect the mimetype
    resource = DataResource(file_location='a/b/test.yoda')
    # First use text content
    assert get_resource_mimetype(resource, 'some text content') == 'text/plain'
    # Then binary content
    assert get_resource_mimetype(resource, 'Binary') == 'application/octet-stream'


def test_get_json_ld(app, load_default_data, identifiers):
    recid = 1
    hepsubmission = get_latest_hepsubmission(publication_recid=recid)
    record = get_record_by_id(recid)

    # Publication metadata
    ctx = format_submission(recid, record, 1, 1, hepsubmission)
    ctx['record_type'] = 'publication'

    publication_data = get_json_ld(ctx, 'finished')
    assert publication_data == {
        '@context': 'http://schema.org',
        'inLanguage': 'en',
        'provider': {
            '@type': 'Organization',
            'name': 'HEPData'
        },
        'publisher': {
            '@type': 'Organization',
            'name': 'HEPData'
        },
        'version': 1,
        'identifier': [
            {'@type': 'PropertyValue',
            'propertyID': 'HEPDataRecord',
            'value': 'http://localhost:5000/record/ins1283842?version=1'},
            {'@type': 'PropertyValue',
                'propertyID': 'HEPDataRecordAlt',
                'value': 'http://localhost:5000/record/1'}
        ],
        'datePublished': '2014',
        '@reverse': {
            'isBasedOn': [
                {
                    '@type': 'ScholarlyArticle',
                    'identifier': {
                        '@type': 'PropertyValue',
                        'propertyID': 'URL',
                        'value': 'https://inspirehep.net/literature/1283842'
                    }
                },
                {
                    '@id': 'https://doi.org/10.1103/PhysRevD.90.072001',
                    '@type': 'JournalArticle'
                }
            ]
        },
        'author': {'@type': 'Organization', 'name': 'D0 Collaboration'},
        'creator': {'@type': 'Organization', 'name': 'D0 Collaboration'},
        '@type': 'Dataset',
        'additionalType': 'Collection',
        '@id': 'https://doi.org/10.17182/hepdata.1.v1',
        'url': 'http://localhost:5000/record/ins1283842?version=1',
        'description': 'Fermilab-Tevatron.  We present measurements of the forward-backward asymmetry, ASYMFB(LEPTON) in the angular distribution of leptons (electrons and muons) from decays of top quarks and antiquarks produced in proton-antiproton collisions. We consider the final state containing a lepton and at least three jets. The entire sample of data collected by the D0 experiment during Run II (2001 - 2011) of the Fermilab Tevatron Collider, corresponding to 9.7 inverse fb of integrated luminosity, is used. We also examine the dependence of ASYMFB(LEPTON) on the transverse momentum, PT(LEPTON), and rapidity, YRAP(LEPTON), of the lepton.',
        'name': 'Measurement of the forward-backward asymmetry in the distribution of leptons in $t\\bar{t}$ events in the lepton+jets channel',
        'hasPart': [
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t1',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) as a function of PT(LEPTON) at reconstruction level.',
            'name': 'Table 1'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t2',
            '@type': 'Dataset',
            'description': 'Observed production-level ASYMFB(LEPTON) as a function of PT(LEPTON).',
            'name': 'Table 2'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t3',
            '@type': 'Dataset',
            'description': 'Observed production-level ASYMFB(LEPTON) as a function of ABS(YRAP(LEPTON)).',
            'name': 'Table 3'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t4',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at reconstruction level for the "lepton + 3 jets, 1 b-tag" channel.',
            'name': 'Table 4'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t5',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at reconstruction level for the "lepton + 3 jets, &gt;= 2 b-tags" channel.',
            'name': 'Table 5'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t6',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at reconstruction level for the "lepton + &gt;= 4 jets, 1 b-tag" channel.',
            'name': 'Table 6'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t7',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at reconstruction level for the "lepton + &gt;= 4 jets, &gt;= 2 b-tags" channel.',
            'name': 'Table 7'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t8',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at production level for the "lepton + 3 jets, 1 b-tag" channel.',
            'name': 'Table 8'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t9',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at production level for the "lepton + 3 jets, &gt;= 2 b-tags" channel.',
            'name': 'Table 9'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t10',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at production level for the "lepton + &gt;= 4 jets, 1 b-tag" channel.',
            'name': 'Table 10'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t11',
            '@type': 'Dataset',
            'description': 'Observed ASYMFB(LEPTON) at production level for the "lepton + &gt;= 4 jets, &gt;= 2 b-tags" channel.',
            'name': 'Table 11'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t12',
            '@type': 'Dataset',
            'description': 'The total value of ASYMFB(LEPTON) at reconstruction level measured from the combined channels.',
            'name': 'Table 12'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t13',
            '@type': 'Dataset',
            'description': 'The total value of ASYMFB(LEPTON) at production level measured from the combined channels.',
            'name': 'Table 13'},
            {'@id': 'https://doi.org/10.17182/hepdata.1.v1/t14',
            '@type': 'Dataset',
            'description': 'The total value of ASYMFB(LEPTON) at production level calculated from the measurements using the combined single lepton channels and a...',
            'name': 'Table 14'}
        ]}

    table_recid = 2
    table_record = get_record_contents(table_recid)
    ctx = format_submission(recid, record,
                            1, 1, hepsubmission,
                            data_table=table_record['title'])
    ctx['record_type'] = 'table'
    ctx['related_publication_id'] = recid
    ctx['table_name'] = record['title']
    ctx['table_id_to_show'] = table_recid

    # Table metadata
    data_submission = DataSubmission.query.filter_by(
        publication_recid=hepsubmission.publication_recid,
        associated_recid=table_recid).first()
    table_data = get_json_ld(ctx, 'finished', data_submission)
    for key in ['@context', 'inLanguage', 'provider', 'publisher', 'version', 'identifier', 'datePublished', '@reverse', 'author', 'creator', '@type']:
        assert table_data[key] == publication_data[key]

    assert table_data['additionalType'] == 'Dataset'
    assert table_data["keywords"] == 'PBAR P --> LEPTON JETS X, ASYM, Inclusive, Asymmetry Measurement, Jet Production, 1960.0'
    assert table_data["url"] == f"http://localhost:5000/record/2"
    assert table_data['distribution'] == [
        {
            '@type': 'DataDownload',
            'contentUrl': f'http://localhost:5000/download/table/2/root',
            'description': 'ROOT file',
            'encodingFormat': 'https://root.cern'
        },
        {
            '@type': 'DataDownload',
            'contentUrl': f'http://localhost:5000/download/table/2/yaml',
            'description': 'YAML file',
            'encodingFormat': 'https://yaml.org'
        },
        {
            '@type': 'DataDownload',
            'contentUrl': f'http://localhost:5000/download/table/2/csv',
            'description': 'CSV file',
            'encodingFormat': 'text/csv'
        },
        {
            '@type': 'DataDownload',
            'contentUrl': f'http://localhost:5000/download/table/2/yoda',
            'description': 'YODA file',
            'encodingFormat': 'https://yoda.hepforge.org'
        },
        {
            '@type': 'DataDownload',
            'contentUrl': f'http://localhost:5000/download/table/2/yoda.h5',
            'description': 'YODA.H5 file',
            'encodingFormat': 'https://yoda.hepforge.org'
        }
    ]
    assert table_data['includedInDataCatalog'] == {
        '@id': 'https://doi.org/10.17182/hepdata.1.v1',
        '@type': 'DataCatalog',
        'url': 'http://localhost:5000/record/ins1283842?version=1'
    }
    assert table_data['isPartOf'] == {
        '@id': publication_data['@id'],
        '@type': publication_data['@type'],
        'description': publication_data['description'],
        'name': publication_data['name'],
        'url': publication_data['url']
    }

    # Resource metadata
    resource = DataResource(
        file_location='a/b/myscript.py',
        file_type='Python',
        file_description='A script to do some stuff to the data',
        doi='10.17182/hepdata.1.v1/r1'
    )
    hepsubmission.resources.append(resource)
    db.session.add(hepsubmission)
    db.session.commit()
    ctx = format_resource(resource, 'print("Hello world")', f'http://localhost:5000/record/resource/{resource.id}?view=true')
    resource_data = get_json_ld(ctx, 'finished')
    for key in ['@context', 'inLanguage', 'provider', 'publisher', 'version', 'identifier', 'datePublished', '@reverse', 'author', 'creator']:
        print(key, resource_data[key])
        assert resource_data[key] == publication_data[key]

    assert resource_data['@id'] == 'https://doi.org/10.17182/hepdata.1.v1/r1'
    assert resource_data['@type'] == "CreativeWork"
    assert resource_data['additionalType'] == 'Python file'
    assert resource_data['contentUrl'] == f'http://localhost:5000/record/resource/{resource.id}?view=true'
    assert resource_data['description'] == resource.file_description
    assert resource_data['name'] == f'"myscript.py" of "{publication_data["name"]}"'
    assert resource_data['url'] == f'http://localhost:5000/record/resource/{resource.id}?landing_page=true'
    assert resource_data['isPartOf'] == table_data['isPartOf']

    # Provide invalid status
    data = get_json_ld(ctx, 'todo')
    assert data == {
        'error': 'JSON-LD is unavailable for this record; JSON-LD is only available for finalised records with DOIs.'
    }

    # Import a record with no collaboration to check authors work as expected
    import_records(['ins47326'], synchronous=True)
    hepsubmission = get_latest_hepsubmission(inspire_id='47326')
    record = get_record_contents(hepsubmission.publication_recid)
    ctx = format_submission(recid, record, 1, 1, hepsubmission)
    ctx['record_type'] = 'publication'

    publication_data = get_json_ld(ctx, 'finished')
    assert publication_data['author'] == [
        {
            "@type": "Person",
            "affiliation": {"@type": "Organization", "name": "Columbia U."},
            "name": "Durbin, R."
        },
        {
            "@type": "Person",
            "affiliation": {"@type": "Organization", "name": "Columbia U."},
            "name": "Loar, H."
        },
        {
            "@type": "Person",
            "affiliation": {"@type": "Organization", "name": "Columbia U."},
            "name": "Steinberger, J."
        }
    ]
    assert publication_data['creator'] == publication_data['author']


def test_create_breadcrumb_text():
    # Test record with first_author
    record = {
        'first_author': {
            'full_name': 'Peppa Pig'
        }
    }
    ctx = {}
    # First with empty authors list
    create_breadcrumb_text([], ctx, record)
    assert ctx == {
        'breadcrumb_text': 'Peppa Pig'
    }

    # Next with multiple authors
    ctx = {}
    create_breadcrumb_text([{'full_name': 'Peppa Pig'}, {'full_name': 'Suzy Sheep'}], ctx, record)
    assert ctx == {
        'breadcrumb_text': 'Peppa Pig et al.'
    }

    # Now empty record, so using authors list
    # First with single author
    ctx = {}
    create_breadcrumb_text([{'full_name': 'Peppa Pig'}], ctx, {})
    assert ctx == {
        'breadcrumb_text': 'Peppa Pig'
    }

    # Next with multiple authors
    ctx = {}
    create_breadcrumb_text([{'full_name': 'Suzy Sheep'}, {'full_name': 'Pedro Pony'}], ctx, {})
    assert ctx == {
        'breadcrumb_text': 'Suzy Sheep et al.'
    }


def update_analyses_single_tool_forgiving(tool):
    """ Call update_analyses_single_tool() but demote known errors to warnings because they are on the tool side."""
    try:
        update_analyses_single_tool(tool)
    except (jsonschema.exceptions.ValidationError, LookupError) as e:
        print(f"WARNING: test_update_analyses[{tool}] failed with '{e}' which indicates error on tool side. Aborting.")
        return False
    return True


base_dir = os.path.dirname(os.path.realpath(__file__))
testdata_analyses = yaml.safe_load(open(os.path.join(base_dir, "test_data", "analyses_tests.yaml"), 'r'))
testdata_analyses_pytest = [tuple([tool]+list(dic.values())) for tool, dic in testdata_analyses.items()]
@pytest.mark.endpoints_test
@pytest.mark.parametrize("tool, import_id, counts, test_user, url, license", testdata_analyses_pytest, ids=testdata_analyses.keys())
def test_update_analyses(app, tool, import_id, counts, test_user, url, license):
    """ Test update of Rivet, MadAnalyses 5, etc. analyses """

    if import_id is not None:
        import_records([f'ins{import_id}'], synchronous=True)

    analysis_resources = DataResource.query.filter_by(file_type=tool).all()
    assert len(analysis_resources) == counts["before"]

    if test_user is not None:
        user = User(**test_user, password="hello1", active=True)
        db.session.add(user)
        db.session.commit()

    if not update_analyses_single_tool_forgiving(tool):
        return

    analysis_resources = DataResource.query.filter_by(file_type=tool).all()
    assert len(analysis_resources) == counts["after"]
    assert analysis_resources[0].file_location == url
    if license is not None:
        assert License.query.filter_by(id=analysis_resources[0].file_license).first().name == license

    if test_user is not None:
        submission = get_latest_hepsubmission(inspire_id=str(import_id), overall_status='finished')
        assert is_current_user_subscribed_to_record(submission.publication_recid, user)


@pytest.mark.endpoints_test
def test_multiupdate_analyses(app):
    """ Test update of analyses multiple times, using Rivet as example """
    # Import a record that already has a Rivet analysis attached (but with '#' in the URL)
    import_records(['ins1203852'], synchronous=True)
    analysis_resources = DataResource.query.filter_by(file_type='rivet').all()
    assert len(analysis_resources) == 1
    assert analysis_resources[0].file_location == 'http://rivet.hepforge.org/analyses#ATLAS_2012_I1203852'

    # Call update_analyses(): should add new resource and delete existing one
    if not update_analyses_single_tool_forgiving('rivet'):
        return
    analysis_resources = DataResource.query.filter_by(file_type='rivet').all()
    assert len(analysis_resources) == 1
    assert analysis_resources[0].file_location == 'http://rivet.hepforge.org/analyses/ATLAS_2012_I1203852'

    # Call update_analyses() again: should be no further changes (but covers more lines of code)
    if not update_analyses_single_tool_forgiving('rivet'):
        return
    analysis_resources = DataResource.query.filter_by(file_type='rivet').all()
    assert len(analysis_resources) == 1
    assert analysis_resources[0].file_location == 'http://rivet.hepforge.org/analyses/ATLAS_2012_I1203852'


@pytest.mark.endpoints_test
def test_update_delete_analyses(app):
    """ Test update and deleting of analyses, using Combine as example """
    # Import a record that has an associated Combine analysis
    import_records(['ins2796231'], synchronous=True)
    analysis_resources = DataResource.query.filter_by(file_type='Combine').all()
    assert len(analysis_resources) == 0
    analysis_resources = DataResource.query.filter_by(file_location='https://doi.org/10.17181/bp9fx-6qs64').all()
    assert len(analysis_resources) == 1
    db.session.delete(analysis_resources[0])  # delete resource so it can be re-added in next step
    db.session.commit()
    if not update_analyses_single_tool_forgiving('Combine'):
        return
    analysis_resources = DataResource.query.filter_by(file_type='Combine').all()
    assert len(analysis_resources) == 1
    assert analysis_resources[0].file_location == 'https://doi.org/10.17181/bp9fx-6qs64'
    assert analysis_resources[0].file_description == 'Statistical models'
    license_data = License.query.filter_by(id=analysis_resources[0].file_license).first()
    assert license_data.name == 'cc-by-4.0'
    assert license_data.url == 'https://creativecommons.org/licenses/by/4.0'


def assert_err_msg(err_type, expected_msg, truncate_length=None):
    err_msg = ""
    try:
        update_analyses_single_tool('TestAnalysis')
    except err_type as e:
        err_msg = str(e)[:truncate_length]
    assert err_msg == expected_msg


@pytest.mark.endpoints_test
def test_incorrect_endpoint(app):
    """ Test update_analyses with incorrect endpoint configurations """
    # Call update_analyses_single_tool using an endpoint with no endpoint_url
    current_app.config["ANALYSES_ENDPOINTS"]["TestAnalysis"] = {}
    assert_err_msg(KeyError, "'No endpoint_url configured for TestAnalysis'")

    # Call update_analyses_single_tool using an invalid endpoint_URL
    current_app.config["ANALYSES_ENDPOINTS"]["TestAnalysis"]['endpoint_url'] = 'https://www.hepdata.net/analyses.json'
    assert_err_msg(LookupError, "Error accessing https://www.hepdata.net/analyses.json, status 404")

    # Call update_analyses_single_tool using an endpoint_url that will fail validation
    current_app.config["ANALYSES_ENDPOINTS"]["TestAnalysis"]['endpoint_url'] = 'https://www.hepdata.net/search/?format=json&size=1'
    assert_err_msg(jsonschema.exceptions.ValidationError, "'facets', 'hits', 'results', 'total' do not match any of the regexes: '^[0-9]+$'", truncate_length=80)

    # Call update_analyses, which doesn't raise exceptions, using an invalid endpoint_URL
    current_app.config["ANALYSES_ENDPOINTS"]["TestAnalysis"]['endpoint_url'] = 'https://www.hepdata.net/analyses.json'
    update_analyses('TestAnalysis')

    # Call forgiving version of update_analyses_single_tool to make sure it works as intended
    assert update_analyses_single_tool_forgiving("TestAnalysis") == False


def test_generate_license_data_by_id(app):
    """
    Tests the generate_license_data_by_id function which
    queries the database for licence information and returns it.
    Also confirms that the default CC0 license will be returned if missing.
    """

    test_cases = [
        {  # Test licence containing junk data
            "id": 1,
            "insert": True,
            "name": "test_license",
            "url": "test_url",
            "description": "test_description"
        },
        {  # Licence which doesnt exist
            "id": 2,
            "insert": True,
            "name": None,
            "url": None,
            "description": None
        },
        {  # Licence which doesnt exist
            "id": 3,
            "insert": False
        },
    ]

    for test in test_cases:
        # If the license is supposed to exist.
        if test["insert"]:
            test_license = License(
                id=test["id"],
                name=test["name"],
                url=test["url"],
                description=test["description"]
            )
            db.session.add(test_license)
            db.session.commit()

        # Run the function based on the ID from the test
        check_license = generate_license_data_by_id(test["id"])

        # If test was supposed to insert, confirm return is the same as insertion
        if test["insert"] and test.get("name") is not None:
            assert check_license == {
                "name": test["name"],
                "url": test["url"],
                "description": test["description"]
            }
        else:
            # Confirm default CC0 text is returned by default
            assert check_license == {
                "name": "CC0",
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "description": ("CC0 enables reusers to distribute, remix, "
                                "adapt, and build upon the material in any "
                                "medium or format, with no conditions.")
            }


def test_get_commit_message(app):
    """
        Tests functionality of the get_commit_message function.
        Ensures that duplicate commit messages
        are handled correctly, and only the most recent
        RecordVersionCommitMessage is returned.
    """
    # We want to ensure duplicate entries
    # We insert V2, as V1 should not be inserted
    test_version, test_recid = 2, 1
    # How many records we want to insert
    insert_amount = 5

    # First we check no insertion, then we check insertion
    for should_insert in [False, True]:
        # Only insert on the second go
        if should_insert:
            # Insert a bunch of duplicate entries
            for i in range(0, insert_amount):
                new_record = RecordVersionCommitMessage(
                    recid=test_recid,
                    version=test_version,
                    # Setting message to a unique value
                    message=str(i)
                )
                db.session.add(new_record)
            db.session.commit()

        # Result of get_commit_message is added to ctx as revision_message
        ctx = {"version": test_version}

        # We always want to check that duplicates are not returned
        try:
            get_commit_message(ctx, test_recid)
        except MultipleResultsFound as e:
            raise AssertionError(e)

        # revision_message only exists if we should insert
        assert ("revision_message" in ctx) == should_insert

        if should_insert:
            # Expected value is max range
            expected_val = insert_amount - 1
            assert ctx["revision_message"]['message'] == str(expected_val)
            assert ctx["revision_message"]['version'] == 2


def test_version_related_functions(app):
    """
    Attempts to bulk test the related functions for both data tables and submissions (records/api):
    Tests the functions:
        - get_related_hepsubmissions
        - get_related_to_this_hepsubmissions
        - get_related_datasubmissions
        - get_related_to_this_datasubmissions
    Tests forward and backward relation for both HEPSubmission and DataSubmission objects, through
    testing the RelatedRecId and RelatedTable relations and querying functions respectively.

    Very similar to e2e/test_records::test_version_related_table, but tests core functionality.
    """

    # Set some random integers to use for record IDs
    random_ints = [random.randint(300, 2147483648) for _ in range(0, 3)]
    # We set alternating record IDs
    test_data = [
        {  # Record 1, which relates to 2
            "recid": random_ints[0],  # This record ID
            "other_recid": random_ints[1],  # Record to relate to
            "overall_status": "finished"  # Chosen HEPSubmission status
        },
        {  # Record 2, which relates to 3
            "recid": random_ints[1],
            "other_recid": random_ints[0],
            "overall_status": "finished"
        },
        {  # Record 3, which relates to 1, but is unfinished
            "recid": random_ints[2],
            "other_recid": random_ints[0],
            "overall_status": "todo"
        }
    ]

    # Insertion of test data
    for test in test_data:
        # We store any HEPSubmission versions in the `test` object
        test["submissions"] = []
        # We also store any related tables data
        test["related_table_data"] = None
        # For each version per test
        for version in range(1, 3):
            new_submission_data = {
                "version": version,
                "submission": HEPSubmission(
                    publication_recid=test["recid"],
                    version=version,
                    overall_status=test["overall_status"]
                ),
                "data_submissions": []
            }

            for table_number in range(1, 3):
                new_datasubmission = {
                    "submission": DataSubmission(
                        doi=f"10.17182/hepdata.{test['recid']}.v{version}/t{table_number}",
                        publication_recid=new_submission_data["submission"].publication_recid,
                        version=new_submission_data["submission"].version  # Also 'v'
                    ),
                    "number": table_number
                }

                new_submission_data["data_submissions"].append(new_datasubmission)
                db.session.add(new_datasubmission["submission"])
            db.session.add(new_submission_data["submission"])
            test["submissions"].append(new_submission_data)

    # Commit now as we need this data for more insertion
    db.session.commit()

    # Now we handle the related data insertion
    for test in test_data:
        latest_submission = test["submissions"][-1]["submission"]
        related_recid = RelatedRecid(this_recid=test["recid"], related_recid=test["other_recid"])
        latest_submission.related_recids.append(related_recid)
        db.session.add_all([related_recid, latest_submission])

        related_table_data = [
            {
                "table_doi": f"10.17182/hepdata.{test['recid']}.v2/t1",
                "related_doi": f"10.17182/hepdata.{test['other_recid']}.v2/t1"
            },
            {
                "table_doi": f"10.17182/hepdata.{test['recid']}.v2/t2",
                "related_doi": f"10.17182/hepdata.{test['other_recid']}.v2/t2"
            },
            {
                "table_doi": f"10.17182/hepdata.{test['recid']}.v2/t2",
                "related_doi": f"10.17182/hepdata.{test['recid']}.v2/t1"
            }
        ]
        test["related_table_data"] = related_table_data

        for related in related_table_data:
            datasub = DataSubmission.query.filter_by(
                doi=related["table_doi"]
            ).first()

            related_datasub = RelatedTable(
                table_doi=related["table_doi"],
                related_doi=related["related_doi"]
            )
            datasub.related_tables.append(related_datasub)
            db.session.add_all([related_datasub, datasub])

    # Finally, we commit all the new data
    db.session.commit()

    # Test case checking
    for test in test_data:
        latest_submission = test["submissions"][-1]
        # Get the HEPSubmission and DataSubmission objects for the test
        test_submission = latest_submission["submission"]
        test_datasubmissions = latest_submission["data_submissions"]

        # Run the HEPSubmission functions to test
        forward_sub_relations = get_related_hepsubmissions(test_submission)
        backward_sub_relations = get_related_to_this_hepsubmissions(test_submission)

        # This record should be referenced by the OTHER record,
        #   and this record should reference the OTHER record
        assert [sub.publication_recid for sub in forward_sub_relations] == [test["other_recid"]]

        expected_backward_sub_relations = []

        # Finished records will have other record references appear
        if test["overall_status"] != "todo":
            expected_backward_sub_relations.append(test["other_recid"])

        assert [sub.publication_recid for sub in backward_sub_relations] == expected_backward_sub_relations

        for test_datasub in test_datasubmissions:
            table_number = test_datasub["number"]
            submission = test_datasub["submission"]

            # Execute the DataSubmission functions to test
            forward_dt_relations = [sub.doi for sub in get_related_datasubmissions(submission)]
            backward_dt_relations = [sub.doi for sub in get_related_to_this_datasubmissions(submission)]

            # The number of entries happens to match the table number
            assert len(forward_dt_relations) == table_number

            # This record should be referenced by the OTHER table,
            #   and this table should reference the OTHER table
            #   (matching the same table number)
            expected_forward_dt_relations = [f"10.17182/hepdata.{test['other_recid']}.v2/t{table_number}"]
            expected_backward_dt_relations = []

            # We expect unfinished records to NOT have `other_recid` tables
            if test["overall_status"] != "todo":
                expected_backward_dt_relations.append(f"10.17182/hepdata.{test['other_recid']}.v2/t{table_number}")

            # Here we expect the second table to reference ITS OWN table one
            if table_number == 2:
                expected_forward_dt_relations.append(f"10.17182/hepdata.{test['recid']}.v2/t1")
            else:
                # For table 1, we expect it to be referenced by the table 2
                expected_backward_dt_relations.append(f"10.17182/hepdata.{test['recid']}.v2/t2")

            # Test that the forward/backward datatable relations work as expected
            assert set(forward_dt_relations) == set(expected_forward_dt_relations)
            assert set(backward_dt_relations) == set(expected_backward_dt_relations)
