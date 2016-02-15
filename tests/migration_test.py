from hepdata.config import CFG_TMPDIR
from hepdata.ext.elasticsearch.api import record_exists
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

            assert publication_information["title"] == test_id["title"]


def test_migration(app, migrator, identifiers):
    print '___test_migration___'
    to_load = [x["inspire_id"] for x in identifiers]
    with app.app_context():
        load_files(to_load)
        id = x["inspire_id"].replace("ins", "")
        assert record_exists(id)
