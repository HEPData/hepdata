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

"""HEPData migration test cases."""

from invenio_records.models import RecordMetadata

import os

from hepdata.ext.elasticsearch.api import get_records_matching_field
from hepdata.modules.records.migrator.api import get_all_ids_in_current_system
from hepdata.modules.records.utils.common import get_record_contents
from hepdata.modules.records.utils.yaml_utils import split_files
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission

__author__ = 'eamonnmaguire'


def test_file_download_and_split(app, migrator, identifiers):
    """___test_file_download_and_split___"""
    with app.app_context():
        for test_id in identifiers:
            temp_file = migrator.download_file(test_id["hepdata_id"])
            assert temp_file is not None

            split_files(
                temp_file, os.path.join(app.config['CFG_TMPDIR'], test_id["hepdata_id"]),
                os.path.join(app.config['CFG_TMPDIR'], test_id[
                    "hepdata_id"] + ".zip"))

            assert (os.path.exists(os.path.join(app.config['CFG_TMPDIR'], test_id["hepdata_id"])))


def test_bad_download_file(app, migrator):
    with app.app_context():
        file = migrator.download_file('xddfsa')
        assert(file is None)


def test_inspire_record_retrieval(app, migrator, identifiers):
    """___test_inspire_record_retrieval___"""
    with app.app_context():
        for test_id in identifiers:
            publication_information, status = \
                migrator.retrieve_publication_information(
                    test_id["hepdata_id"])

            assert publication_information["title"] == test_id["title"]
            assert status == "success"


def test_migration(app, load_default_data, identifiers):
    print('___test_migration___')
    with app.app_context():
        records = RecordMetadata.query.all()
        all_exist = True
        total_expected_records = 0
        for test_record_info in identifiers:
            found = False
            total_expected_records += (test_record_info['data_tables'] + 1)

            for record in records:
                if record.json['inspire_id'] == test_record_info['inspire_id']:
                    found = True
                    break
            all_exist = found

        assert (total_expected_records == len(records))
        assert (all_exist)


def test_load_file(app, migrator):
    print('___test_load_file___')
    with app.app_context():
        success = migrator.load_file('ins1487726')
        assert (success)

        hepsubmission = get_latest_hepsubmission(inspire_id='1487726')

        assert(hepsubmission is not None)
        assert (hepsubmission.inspire_id == '1487726')

        index_records = get_records_matching_field('inspire_id', hepsubmission.inspire_id, doc_type='publication')
        assert (len(index_records['hits']['hits']) == 1)

        publication_record = get_record_contents(hepsubmission.publication_recid)
        assert (publication_record is not None)

        data_submissions = DataSubmission.query.filter_by(
            publication_recid=hepsubmission.publication_recid).count()
        assert (data_submissions == 5)


def test_get_ids_in_current_system():
    ids = get_all_ids_in_current_system()

    assert (ids is not None)
