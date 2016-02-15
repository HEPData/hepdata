from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.workflow import update_record, create_record


def test_file_download_and_split(app, migrator, identifiers):
    """___test_file_download_and_split___"""
    with app.app_context():
        record_information = create_record({'journal_info': 'Phys. Letts', 'title': 'My Journal Paper'})

        record = get_record_by_id(record_information['recid'])
        print(record)
        assert (record['title'] == 'My Journal Paper')
        assert (record['journal_info'] == 'Phys. Letts')
        update_record(record_information['recid'], {'journal_info': 'test'})

        updated_record = get_record_by_id(record_information['recid'])
        assert (updated_record['journal_info'] == 'test')
