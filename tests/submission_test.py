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

import logging
import os
import shutil
import time
from time import sleep

from invenio_db import db
import pytest

from hepdata.ext.elasticsearch.api import get_records_matching_field
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.api import format_submission, process_saved_file, create_new_version
from hepdata.modules.records.utils.common import infer_file_type, contains_accepted_url, allowed_file, record_exists, \
    get_record_contents, is_histfactory
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import process_submission_directory, do_finalise, unload_submission
from hepdata.modules.submission.api import get_latest_hepsubmission, get_submission_participants_for_record
from hepdata.modules.submission.models import DataSubmission, HEPSubmission
from hepdata.modules.submission.views import process_submission_payload


def test_submission_endpoint(app, client):
    submission = process_submission_payload(title="Test Submission", submitter_id=1,
                                            reviewer={'name': 'Reviewer', 'email': 'reviewer@hepdata.net'},
                                            uploader={'name': 'Uploader', 'email': 'uploader@hepdata.net'},
                                            send_upload_email=False)

    assert (submission is not None)


def test_allowed_file():
    assert (allowed_file('test.zip'))
    assert (allowed_file('test.tar'))
    assert (allowed_file('test.tar.gz'))
    assert (not allowed_file('test.pdf'))


def test_url_pattern():
    test_urls = [
        {"url": "http://rivet.hepforge.org/analyses/ATLAS_2012_I1203852",
         "exp_result": "rivet"},
        {"url": "https://bitbucket.org/eamonnmag/automacron-evaluation",
         "exp_result": "bitbucket"},
        {"url": "http://sourceforge.net/projects/isacommons/",
         "exp_result": "sourceforge"},
        {"url": "http://zenodo.net/record/11085", "exp_result": "zenodo"},
        {"url": "https://github.com/HEPData/hepdata",
         "exp_result": "github"}
    ]

    for url_group in test_urls:
        contained, url_type = contains_accepted_url(url_group["url"])
        assert (url_group["exp_result"] == url_type)


@pytest.mark.parametrize("filename,description,type,expected",
    [
        ("pyhf.tar.gz", "PyHF", None, True),
        ("pyhf.tgz", "File containing likelihoods", None, True),
        ("pyhf.zip", "HistFactory JSON file", None, True),
        ("test.zip", "Some sort of file", "HistFactory", True),
        ("test.zip", "Some sort of file", "histfactory", True),
        ("pyhf.tar.gz", "A file", None, False),
        ("pyhf.json", "HistFactory JSON file", None, True),
        ("test.zip", "Some sort of file", "json", False),
    ]
)
def test_is_histfactory(filename, description, type, expected):
    assert is_histfactory(filename, description, type) == expected


@pytest.mark.parametrize("filename,description,type,expected",
    [
        ("somesortofresource", "", None, "resource"),
        ("https://github.com/HEPData/hepdata", "", None, "github"),
        ("test.py", "", None, "Python"),
        ("test.cpp", "", None, "C++"),
        ("test.c", "", None, "C"),
        ("test.sh", "", None, "Bash Shell"),
        ("test.root", "", None, "ROOT"),
        ("test.docx", "", None, "docx"),
        ("test", "", None, "resource"),
        ("pyhf.tgz", "File containing likelihoods", None, "HistFactory"),
        ("test.zip", "Some sort of file", "HistFactory", "HistFactory")
    ]
)
def test_infer_file_type(filename, description, type, expected):
    assert infer_file_type(filename, description, type) == expected


def test_get_submission_participants(app, load_default_data, identifiers):
    hepsubmission = get_latest_hepsubmission(inspire_id=identifiers[0]["inspire_id"])

    # Should initially be 1 participant, imported from the submission yaml doc
    participants = get_submission_participants_for_record(hepsubmission.publication_recid)
    assert len(participants) == 1
    assert participants[0].publication_recid == hepsubmission.publication_recid
    assert participants[0].email is None
    assert participants[0].user_account is None
    assert participants[0].full_name == "Stephen Webster"
    assert participants[0].status == "reserve"
    assert participants[0].role == "Encoded"

    # Add a participant
    new_participant = SubmissionParticipant(
        publication_recid=hepsubmission.publication_recid,
        email="test@hepdata.net",
        full_name="Test User",
        status="primary",
        role="uploader"
    )
    db.session.add(new_participant)
    db.session.commit()

    # Get participants again
    participants = get_submission_participants_for_record(hepsubmission.publication_recid)
    assert len(participants) == 2
    assert participants[0].publication_recid == hepsubmission.publication_recid
    assert participants[0].email is None
    assert participants[0].user_account is None
    assert participants[0].full_name == "Stephen Webster"
    assert participants[0].status == "reserve"
    assert participants[0].role == "Encoded"
    assert participants[1].publication_recid == hepsubmission.publication_recid
    assert participants[1].email == "test@hepdata.net"
    assert participants[1].user_account is None
    assert participants[1].full_name == "Test User"
    assert participants[1].status == "primary"
    assert participants[1].role == "uploader"

    # Get participants with additional filter
    participants = get_submission_participants_for_record(
        hepsubmission.publication_recid, status="primary")
    assert len(participants) == 1
    assert participants[0].publication_recid == hepsubmission.publication_recid
    assert participants[0].email == "test@hepdata.net"
    assert participants[0].user_account is None
    assert participants[0].full_name == "Test User"
    assert participants[0].status == "primary"
    assert participants[0].role == "uploader"

    # Get participants with multiple roles
    participants = get_submission_participants_for_record(
        hepsubmission.publication_recid, roles=['uploader', 'Encoded'])
    assert len(participants) == 2
    participants = get_submission_participants_for_record(
        hepsubmission.publication_recid, roles=['uploader'])
    assert len(participants) == 1
    assert participants[0].full_name == "Test User"
    participants = get_submission_participants_for_record(
        hepsubmission.publication_recid, roles=['reviewer'])
    assert len(participants) == 0


def test_create_submission(app, admin_idx):
    """
    Test the whole submission pipeline in loading a file, ensuring the HEPSubmission object is created,
    all the files have been added, and the record has been indexed.
    :return:
    """
    with app.app_context():

        admin_idx.recreate_index()

        # test submission part works

        record = {'inspire_id': '19999999',
                  'title': 'HEPData Testing 1',
                  'reviewer': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'uploader': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'message': 'This is ready',
                  'user_id': 1}

        hepdata_submission = process_submission_payload(**record)

        assert (hepdata_submission.version == 1)
        assert (hepdata_submission.overall_status == 'todo')

        # test upload works
        base_dir = os.path.dirname(os.path.realpath(__file__))

        test_directory = os.path.join(base_dir, 'test_data/test_submission')
        time_stamp = str(int(round(time.time())))
        directory = get_data_path_for_record(hepdata_submission.publication_recid, time_stamp)
        shutil.copytree(test_directory, directory)
        assert(os.path.exists(directory))

        process_submission_directory(directory, os.path.join(directory, 'submission.yaml'),
                                     hepdata_submission.publication_recid)

        admin_idx_results = admin_idx.search(term=hepdata_submission.publication_recid, fields=['recid'])
        assert(admin_idx_results is not None)

        data_submissions = DataSubmission.query.filter_by(
            publication_recid=hepdata_submission.publication_recid).count()
        assert (data_submissions == 8)
        assert (len(hepdata_submission.resources) == 4)
        participants = get_submission_participants_for_record(hepdata_submission.publication_recid)
        assert (len(participants) == 4)

        do_finalise(hepdata_submission.publication_recid, force_finalise=True, convert=False)

        assert (record_exists(inspire_id=record['inspire_id']))

        # Test record and data submissions are in index...
        index_records = get_records_matching_field('inspire_id', record['inspire_id'], doc_type='publication')
        assert (len(index_records['hits']['hits']) == 1)
        data_index_records = get_records_matching_field('inspire_id', record['inspire_id'], doc_type='datatable')
        assert (len(data_index_records['hits']['hits']) == 8)

        publication_record = get_record_contents(hepdata_submission.publication_recid)

        assert (publication_record is not None)

        ctx = format_submission(hepdata_submission.publication_recid, publication_record, hepdata_submission.version, 1,
                                hepdata_submission)

        assert(ctx is not None)

        assert(ctx['version'] == 1)
        assert (ctx['recid'] == hepdata_submission.publication_recid)

        # Create a new version of the submission
        create_new_version(hepdata_submission.publication_recid, None)
        hepdata_submission_v2 = get_latest_hepsubmission(inspire_id='19999999')
        assert(hepdata_submission_v2.version == 2)
        assert(hepdata_submission_v2.overall_status == 'todo')

        # Upload the same data (so table names are the same)
        time_stamp2 = str(int(round(time.time())+1)) # add 1 to make sure it's a different timestamp
        directory2 = get_data_path_for_record(hepdata_submission_v2.publication_recid, time_stamp2)
        shutil.copytree(test_directory, directory2)
        assert(os.path.exists(directory2))

        errors = process_submission_directory(directory2, os.path.join(directory2, 'submission.yaml'),
                                     hepdata_submission_v2.publication_recid)
        data_submissions = DataSubmission.query.filter_by(
            publication_recid=hepdata_submission.publication_recid).all()
        assert (len(data_submissions) == 16)
        assert (len(hepdata_submission_v2.resources) == 4)

        do_finalise(hepdata_submission_v2.publication_recid, force_finalise=True, convert=False)

        # Associated recids should be unique across both versions
        associated_recids = [d.associated_recid for d in data_submissions]
        # Set size should be the same as list length if values are unique
        assert (len(set(associated_recids)) == len(associated_recids))

        # Index should contain the latest data
        index_records = get_records_matching_field('inspire_id', record['inspire_id'], doc_type='publication')
        assert (len(index_records['hits']['hits']) == 1)
        data_index_records = get_records_matching_field('inspire_id', record['inspire_id'], doc_type='datatable')
        assert (len(data_index_records['hits']['hits']) == 8)
        data_index_recids = [x['_source']['recid'] for x in data_index_records['hits']['hits']]

        data_submission_v2_recids = [d.associated_recid for d in data_submissions if d.version == 2]
        assert set(data_index_recids) == set(data_submission_v2_recids)

        # remove the submission and test that all is remove
        # First unload latest (v2) submission
        unload_submission(hepdata_submission_v2.publication_recid, version=2)
        hepdata_submission = get_latest_hepsubmission(inspire_id='19999999')
        assert (hepdata_submission.version == 1)

        # Now unload v1
        unload_submission(hepdata_submission.publication_recid)

        assert (not record_exists(inspire_id=record['inspire_id']))

        data_submissions = DataSubmission.query.filter_by(
            publication_recid=hepdata_submission.publication_recid).count()

        assert (data_submissions == 0)

        participant_count = SubmissionParticipant.query.filter_by(
            publication_recid=hepdata_submission.publication_recid).count()
        assert(participant_count == 0)

        sleep(2)

        admin_idx_results = admin_idx.search(term=hepdata_submission.publication_recid, fields=['recid'])
        assert (len(admin_idx_results) == 0)

        # Check file dir has been deleted
        assert(not os.path.exists(directory))


def test_old_submission_yaml(app, admin_idx):
    """
    Test we can validate against the old submission schema (for use when importing)
    :return:
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='todo',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    directory = os.path.join(base_dir, 'test_data/test_v0_submission')

    # This should fail against current schema
    errors = process_submission_directory(directory,
                                          os.path.join(directory, 'submission.yaml'),
                                          12345)
    assert('submission.yaml' in errors)
    assert(len(errors['submission.yaml']) == 2)
    assert(errors['submission.yaml'][0]['level'] == 'error')
    assert(errors['submission.yaml'][0]['message'].startswith(
        "submission.yaml is invalid HEPData YAML"
    ))
    assert(errors['submission.yaml'][1]['level'] == 'error')
    assert(errors['submission.yaml'][1]['message'].startswith(
        "Invalid value (in GeV) for cmenergies: '1.383-1.481 GeV'"
    ))

    # Use old schema - should now work
    errors = process_submission_directory(directory,
                                          os.path.join(directory, 'submission.yaml'),
                                          12345,
                                          old_schema=True)
    assert(errors == {})


def test_submission_no_additional_info(app):
    """
    Test we can submit a submission with no additional info in submission.yaml
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='todo',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()
    previous_last_updated = hepsubmission.last_updated

    directory = os.path.join(base_dir, 'test_data/test_submission_no_additional_info')
    errors = process_submission_directory(
        directory,
        os.path.join(directory, 'submission.yaml'),
        12345
    )

    assert(errors == {})
    # last_updated should have been updated (by a few milliseconds)
    assert hepsubmission.last_updated > previous_last_updated


def test_invalid_submission_yaml(app, admin_idx):
    """
    Test the right thing happens when the submission.yaml is invalid
    :return:
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    directory = os.path.join(base_dir, 'test_data/test_invalid_submission_file')
    errors = process_submission_directory(directory,
                                       os.path.join(directory, 'submission.yaml'),
                                       12345)

    assert('submission.yaml' in errors)
    assert(len(errors['submission.yaml']) == 1)
    assert(errors['submission.yaml'][0]['level'] == 'error')
    assert(errors['submission.yaml'][0]['message'].startswith("There was a problem parsing the file"))


def test_invalid_data_yaml(app, admin_idx):
    """
    Test the right thing happens when a data yaml file is invalid
    :return:
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='todo',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    directory = os.path.join(base_dir, 'test_data/test_invalid_data_file')
    errors = process_submission_directory(directory,
                                       os.path.join(directory, 'submission.yaml'),
                                       12345)

    assert('data1.yaml' in errors)
    assert(len(errors['data1.yaml']) == 1)
    assert(errors['data1.yaml'][0]['level'] == 'error')
    assert(errors['data1.yaml'][0]['message'].startswith("There was a problem parsing the file"))


def test_submission_too_big(app, mocker):
    """
    Test the right thing happens when the submission data is too big
    :return:
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='todo',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    # Patch the app config to reduce the max upload size
    mocker.patch.dict('flask.current_app.config',
                      {'CONVERT_MAX_SIZE': 1000})

    test_directory = os.path.join(base_dir, 'test_data/test_submission')
    errors = process_submission_directory(
        test_directory,
        os.path.join(test_directory, 'submission.yaml'),
        12345
    )

    assert('Archive' in errors)
    assert(len(errors['Archive']) == 1)
    assert(errors['Archive'][0]['level'] == 'error')
    assert(errors['Archive'][0]['message'].startswith("Archive is too big for conversion to other formats."))


def test_duplicate_table_names(app):
    """
    Test that an error is returned for a submission.yaml file with duplicate table names.
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))

    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='todo',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    directory = os.path.join(base_dir, 'test_data/test_duplicate_table_names')
    errors = process_submission_directory(directory,
                                       os.path.join(directory, 'submission.yaml'),
                                       12345)

    assert('submission.yaml' in errors)
    assert(len(errors['submission.yaml']) == 5)
    assert(errors['submission.yaml'][0]['level'] == 'error')
    assert(errors['submission.yaml'][0]['message'].startswith("submission.yaml is invalid HEPData YAML"))
    assert(errors['submission.yaml'][1]['level'] == 'error')
    assert(errors['submission.yaml'][1]['message'].startswith("Duplicate table name"))
    assert(errors['submission.yaml'][2]['level'] == 'error')
    assert(errors['submission.yaml'][2]['message'].startswith("Duplicate table name"))
    assert(errors['submission.yaml'][3]['level'] == 'error')
    assert(errors['submission.yaml'][3]['message'].startswith("Duplicate table data_file"))
    assert(errors['submission.yaml'][4]['level'] == 'error')
    assert(errors['submission.yaml'][4]['message'].startswith("Duplicate table data_file"))


def test_status_reset(app, mocker):
    """
    Test that the status is reset if something unexpected goes wrong
    :return:
    """

    base_dir = os.path.dirname(os.path.realpath(__file__))
    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='processing',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    assert(hepsubmission.overall_status == 'processing')

    mocker.patch('hepdata.modules.records.api.process_zip_archive',
                 side_effect=Exception("Something went wrong"))

    zip_file = os.path.join(base_dir, 'test_data/TestHEPSubmission.zip')
    process_saved_file(zip_file, 12345, 1, '', 'todo')

    # After initial failure, overall_status should be reset to 'todo'
    assert(hepsubmission.overall_status == 'todo')


def test_status_reset_error(app, mocker, caplog):
    """
    Test that an error is logged if something goes wrong in the status reset
    :return:
    """
    caplog.set_level(logging.ERROR)
    base_dir = os.path.dirname(os.path.realpath(__file__))
    hepsubmission = HEPSubmission(publication_recid=12345,
                                  overall_status='processing',
                                  version=1)
    db.session.add(hepsubmission)
    db.session.commit()

    assert(hepsubmission.overall_status == 'processing')

    mocker.patch('hepdata.modules.records.api.process_zip_archive',
                 side_effect=Exception("Something went wrong"))
    mocker.patch('hepdata.modules.records.api.cleanup_submission',
                 side_effect=Exception("Could not clean up the submission"))

    zip_file = os.path.join(base_dir, 'test_data/TestHEPSubmission.zip')
    process_saved_file(zip_file, 12345, 1, '', 'todo')

    # After initial failure, overall_status has not been able to be reset
    assert(hepsubmission.overall_status == 'processing')
    assert(len(caplog.records) == 1)

    assert(caplog.records[0].levelname == "ERROR")
    assert(caplog.records[0].msg
           == "Exception while cleaning up: Could not clean up the submission")
