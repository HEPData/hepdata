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
            file = migrator.download_file(test_id["inspire_id"])
            assert file is not None

            migrator.split_files(
                file, os.path.join(CFG_TMPDIR, test_id["inspire_id"]),
                os.path.join(CFG_TMPDIR, test_id[
                    "inspire_id"] + ".zip"))


def test_inspire_record_retrieval(app, migrator, identifiers):
    """___test_inspire_record_retrieval___"""
    with app.app_context():
        for test_id in identifiers:
            publication_information = \
                migrator.retrieve_publication_information(
                    test_id["inspire_id"])

            print publication_information["title"]
            assert publication_information["title"] == test_id["title"]


def test_migration(app, migrator, identifiers):
    print '___test_migration___'
    to_load = [x["inspire_id"] for x in identifiers]
    with app.app_context():
        load_files(to_load, synchronous=True)

        records = RecordMetadata.query.all()
        all_exist = True
        total_expected_records = 0
        for test_record_info in identifiers:
            found = False
            total_expected_records += (test_record_info['data_tables']+1)
            cleaned_record_id = int(test_record_info['inspire_id'].replace("ins", ""))
            for record in records:
                if record.json['inspire_id'] == cleaned_record_id:
                    found = True
                    break
            all_exist = found

        assert(total_expected_records == len(records))
        assert(all_exist)
