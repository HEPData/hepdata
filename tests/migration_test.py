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

from hepdata.config import CFG_TMPDIR
from hepdata.modules.records.migrator.api import load_files
import os

__author__ = 'eamonnmaguire'


def test_file_download_and_split(app, migrator, identifiers):
    """___test_file_download_and_split___"""
    with app.app_context():
        for test_id in identifiers:
            print test_id["inspire_id"]
            file = migrator.download_file(test_id["hepdata_id"])
            assert file is not None

            migrator.split_files(
                file, os.path.join(CFG_TMPDIR, test_id["hepdata_id"]),
                os.path.join(CFG_TMPDIR, test_id[
                    "hepdata_id"] + ".zip"))


def test_inspire_record_retrieval(app, migrator, identifiers):
    """___test_inspire_record_retrieval___"""
    with app.app_context():
        for test_id in identifiers:
            publication_information = \
                migrator.retrieve_publication_information(
                    test_id["hepdata_id"])

            print publication_information["title"]
            assert publication_information["title"] == test_id["title"]


def test_migration(app, migrator, identifiers):
    print '___test_migration___'
    to_load = [x["hepdata_id"] for x in identifiers]
    with app.app_context():
        load_files(to_load, synchronous=True)

        records = RecordMetadata.query.all()
        all_exist = True
        total_expected_records = 0
        for test_record_info in identifiers:
            found = False
            total_expected_records += (test_record_info['data_tables']+1)

            for record in records:
                if record.json['inspire_id'] == test_record_info['inspire_id']:
                    found = True
                    break
            all_exist = found

        assert(total_expected_records == len(records))
        assert(all_exist)
