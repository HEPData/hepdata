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

import os
import shutil
import time
from time import sleep

from invenio_db import db

from hepdata.ext.elasticsearch.api import get_records_matching_field
from hepdata.modules.records.api import format_submission
from hepdata.modules.records.utils.common import infer_file_type, contains_accepted_url, allowed_file, record_exists, \
    get_record_contents
from hepdata.modules.records.utils.data_files import get_data_path_for_record
from hepdata.modules.records.utils.submission import process_submission_directory, do_finalise, unload_submission
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


def test_file_extension_pattern():
    test_files = [
        {"file": "test.py", "exp_result": "Python"},
        {"file": "test.cpp", "exp_result": "C++"},
        {"file": "test.c", "exp_result": "C"},
        {"file": "test.sh", "exp_result": "Bash Shell"},
        {"file": "test.root", "exp_result": "ROOT"},
        {"file": "test.docx", "exp_result": "docx"},
        {"file": "test", "exp_result": "resource"}
    ]

    for file_group in test_files:
        extension = infer_file_type(file_group["file"])
        assert (file_group["exp_result"] == extension)


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
        assert (len(hepdata_submission.participants) == 4)

        do_finalise(hepdata_submission.publication_recid, force_finalise=True, convert=False)

        assert (record_exists(inspire_id=record['inspire_id']))

        # Test record is in index...
        index_records = get_records_matching_field('inspire_id', record['inspire_id'], doc_type='publication')
        assert (len(index_records['hits']['hits']) == 1)

        publication_record = get_record_contents(hepdata_submission.publication_recid)

        assert (publication_record is not None)

        ctx = format_submission(hepdata_submission.publication_recid, publication_record, hepdata_submission.version, 1,
                                hepdata_submission)

        assert(ctx is not None)

        assert(ctx['version'] == 1)
        assert (ctx['recid'] == hepdata_submission.publication_recid)

        # remove the submission and test that all is remove

        unload_submission(hepdata_submission.publication_recid)

        assert (not record_exists(inspire_id=record['inspire_id']))

        data_submissions = DataSubmission.query.filter_by(
            publication_recid=hepdata_submission.publication_recid).count()

        assert (data_submissions == 0)

        sleep(2)

        admin_idx_results = admin_idx.search(term=hepdata_submission.publication_recid, fields=['recid'])
        assert (len(admin_idx_results) == 0)

        # Check file dir has been deleted
        assert(not os.path.exists(directory))


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
