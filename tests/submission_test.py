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
import os
import shutil
import time
from datetime import datetime
from time import sleep
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import NoResultFound

from invenio_db import db
import pytest

from hepdata.ext.opensearch.api import get_records_matching_field
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.records.api import (
    create_new_version,
    format_submission,
    get_record_data_list,
    get_related_datasubmissions,
    get_related_hepsubmissions,
    get_related_to_this_datasubmissions,
    get_related_to_this_hepsubmissions,
    get_table_data_list,
    process_saved_file, get_commit_message
)
from hepdata.modules.records.utils.common import infer_file_type, contains_accepted_url, allowed_file, record_exists, \
    get_record_contents, is_histfactory, get_record_by_id
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import process_submission_directory, do_finalise, unload_submission, \
    cleanup_data_related_recid
from hepdata.modules.submission.api import get_latest_hepsubmission, get_submission_participants_for_record
from hepdata.modules.submission.models import DataSubmission, HEPSubmission, RelatedRecid, RecordVersionCommitMessage
from hepdata.modules.submission.views import process_submission_payload
from hepdata.config import HEPDATA_DOI_PREFIX
from tests.conftest import create_test_record


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


def test_related_records(app, admin_idx):
    """
    Test uploading of submission directories with values
    for related record IDs and data table entries with related
    doi entries.
    Checks submissions are correctly inserted, and linking
    occurs.
    :return:
    """
    with app.app_context():
        admin_idx.recreate_index()
        # The directories containing the test data
        test_dir = "test_data/related_submission_test/"
        # First two are valid, and relate to each other
        # 3 has invalid record entry (a string), 4 has invalid data DOI string (doesn't match regex)
        test_data = [
            {"dir": "related_submission_1",
                "related": 2,
                "record_title": "Title 1",
                "expected_title": "Title 2",
                "expected_version": 1},
            {"dir": "related_submission_2",
                "related": 1,
                "record_title": "Title 2",
                "expected_title": "Title 1",
                "expected_version": 1},
            {"dir": "related_submission_3", "related": None, "record_title": "Title 3"},
            {"dir": "related_submission_4", "related": None, "record_title": "Title 4"}
        ]
        # Dummy record data
        # The title will be set later based on test_data values
        record = {'title': None,
                  'reviewer': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'uploader': {'name': 'Testy McTester', 'email': 'test@test.com'},
                  'message': 'This is ready',
                  'user_id': 1}
        base_dir = os.path.dirname(os.path.realpath(__file__))

        # Begin submission of test submissions
        for data in test_data:
            # Set up a new test submission
            record['title'] = data['record_title']
            data['sub'] = process_submission_payload(**record)
            test_sub = data['sub']
            # Ensure the status is set to `finished` so the related data can be accessed.
            test_sub.overall_status = 'finished'
            test_directory = os.path.join(base_dir, test_dir, data['dir'])
            record_dir = get_data_path_for_record(test_sub.publication_recid, str(int(round(time.time()))))
            shutil.copytree(test_directory, record_dir)
            process_submission_directory(record_dir, os.path.join(record_dir, 'submission.yaml'),
                                test_sub.publication_recid)

        # Checking against results in test_data
        for data in test_data:
            submission = data['sub']
            # Set some test criteria based on the current data.
            # If related_id is None, then some tests should yield empty lists.
            submission_count, table_count = (1, 3) if data['related'] is not None else (0, 0)

            related_hepsubmissions = get_related_hepsubmissions(submission)
            related_to_this_hepsubmissions = get_related_to_this_hepsubmissions(submission)

            # Check that the correct amount of objects are returned from the queries.
            assert len(submission.related_recids) == submission_count
            assert len(related_to_this_hepsubmissions) == submission_count
            assert len(related_hepsubmissions) == submission_count

            related_record_data = get_record_data_list(submission, "related")
            related_to_this_record_data = get_record_data_list(submission, "related_to_this")

            assert len(related_record_data) == submission_count
            assert len(related_to_this_record_data) == submission_count

            if data['related']:
                assert int(related_hepsubmissions[0].publication_recid) == data['related']
                assert int(related_to_this_hepsubmissions[0].publication_recid) == data['related']

                expected_record_data = [{
                    "recid": data['related'],
                     "title": data['expected_title'],
                     "version": data['expected_version']
                }]
                assert related_record_data == expected_record_data
                assert related_to_this_record_data == expected_record_data

            for related_table in submission.related_recids:
                # Get all other RelatedTable entries related to this one
                # and check against the expected value in `data`
                assert related_table.related_recid == data['related']
            for related_hepsub in related_to_this_hepsubmissions:
                # Get all other submissions related to this one
                # and check against the expected value in `data`
                assert related_hepsub.publication_recid == data['related']

            # DataSubmission DOI checking
            # Get the data for the current test DataSubmission object
            data_submissions = DataSubmission.query.filter_by(publication_recid=submission.publication_recid).all()
            # Check against the expected amount of related objects as defined above
            assert len(data_submissions) == table_count
            for s in range(0, len(data_submissions)):
                data_submission = data_submissions[s]
                # Set the current table number for checking
                tablenum = s + 1
                # Generate the test DOI
                doi_check = f"{HEPDATA_DOI_PREFIX}/hepdata.{data['related']}.v1/t{tablenum}"
                # Generate the expected table data
                expected_table_data = [{"name": f"Table {tablenum}",
                                        "doi": doi_check,
                                        "description": f"Test Table {tablenum}"}]

                # Execute the related data functions
                # The table data functions generate a dictionary for tooltip data for each contained entry.
                # The submission.get_related functions test that the related objects are found as expected.
                related_datasubmissions = get_related_datasubmissions(data_submission)
                related_to_this_datasubmissions = get_related_to_this_datasubmissions(data_submission)
                related_table_data = get_table_data_list(data_submission, "related")
                related_to_this_table_data = get_table_data_list(data_submission,"related_to_this")

                # Check that the get related functions are returning the correct amount of objects.
                # Based on the current tests, this is either 0, or 3
                assert len(related_datasubmissions) == submission_count
                assert len(related_to_this_datasubmissions) == submission_count
                assert len(related_table_data) == submission_count
                assert len(related_to_this_table_data) == submission_count

                if data['related']:
                    assert related_table_data == expected_table_data
                    assert related_to_this_table_data == expected_table_data

                # Test doi_check against the related DOI list.
                for related in related_datasubmissions:
                    assert doi_check == related.doi


def test_cleanup_data_related_recid(app, admin_idx):
    """
    Insert a related record ID entry and test that the cleanup function will
    remove all RelatedRecid objects.
    :return:
    """
    # The test record ID to use
    recid = 123123
    # Creating the dummy submission and related record ID entry
    hepsubmission = HEPSubmission(publication_recid=recid,
                                  overall_status='todo',
                                  version=1)
    related = RelatedRecid(this_recid=recid, related_recid=1)
    hepsubmission.related_recids.append(related)
    db.session.add_all([related, hepsubmission])
    db.session.commit()

    # Check that there is one related record ID
    check_submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
    assert len(check_submission.related_recids) == 1

    # Run the cleanup function to test
    cleanup_data_related_recid(recid)

    # Query and check that there are no submissions
    check_submission = HEPSubmission.query.filter_by(publication_recid=recid).first()
    assert len(check_submission.related_recids) == 0


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


# Patching to force no-op on function: process_last_updates()
@patch("hepdata.ext.opensearch.document_enhancers.process_last_updates")
def test_do_finalise_commit_message(app, admin_idx):
    """
    Tests the do_finalise function.

    Here we are testing the commit message functionality, ensuring proper rollback in the event of an error.
    """

    # Insert the testing record data
    with app.app_context():
        admin_idx.recreate_index()
        # Create test submission/record
        hepdata_submission = create_test_record(
            os.path.abspath('tests/test_data/test_submission'),
            overall_status='todo'
        )

        # We're going to add an extra commit message
        conflicting_record = RecordVersionCommitMessage(
            recid=hepdata_submission.publication_recid,
            version=hepdata_submission.version,
            message="OldMessage"
        )

        db.session.add(conflicting_record)
        db.session.commit()

        # Create record data and prepare
        record = get_record_by_id(hepdata_submission.publication_recid)
        record["creation_date"] = str(datetime.today().strftime('%Y-%m-%d'))

        # Now we mock the get_record_by_id function to cause an error.
        with patch("hepdata.modules.records.utils.submission.get_record_by_id") as mock_get_record:
            class MockRecord(MagicMock, dict):
                # Mocking the invenio-records Record class
                # Used to create a mock also of type dict
                pass

            # Create mock record object, set its value
            # and set it to cause an error.
            mock_record = MockRecord()
            mock_get_record.return_value = mock_record
            # Set the record to raise exception when commit() is called
            mock_record.commit.side_effect = NoResultFound()
            # Injecting specific dictionary keys to avoid error.
            mock_record.__getitem__.side_effect = lambda key: 1 if key == 'item_doi' else None

            # Now we run the do_finalise function (PATCHED)
            result = do_finalise(
                        hepdata_submission.publication_recid,
                        publication_record=record,
                        commit_message="NewMessage",
                        force_finalise=True,
                        convert=False
            )
            # Convert str(json)->dict
            result = json.loads(result)

        # Get all commit messages
        commit_messages = RecordVersionCommitMessage.query.filter_by(
            recid=hepdata_submission.publication_recid
        ).all()

        # Ensure that no new messages have inserted
        assert len(commit_messages) == 1
        assert commit_messages[0].message == "OldMessage"

        # Confirm that the result response exists and is correct
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert result["errors"][0] == "No record found to update. Which is super strange."

        # Run do_finalise again, but UNPATCHED
        result = do_finalise(
            hepdata_submission.publication_recid,
            publication_record=record,
            commit_message="NewMessage",
            force_finalise=True,
            convert=False
        )
        # Convert str(json)->dict
        result = json.loads(result)

        # Get the commit messages
        commit_messages = RecordVersionCommitMessage.query.filter_by(
            recid=hepdata_submission.publication_recid
        ).all()

        # `NewMessage` should have inserted, and no error found.
        assert len(commit_messages) == 2
        assert commit_messages[-1].message == "NewMessage"
        assert "errors" not in result
