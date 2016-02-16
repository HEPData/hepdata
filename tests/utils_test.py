from hepdata.utils.miscellanous import splitter


def test_utils():
    docs = [{'id': 1, 'type': 'publication'},
            {'related_publication': 1, 'id': 2, 'type': 'data_table'},
            {'related_publication': 1, 'id': 3, 'type': 'data_table'},
            {'related_publication': 1, 'id': 4, 'type': 'data_table'},
            {'related_publication': 1, 'id': 5, 'type': 'data_table'},
            {'related_publication': 1, 'id': 6, 'type': 'data_table'},
            {'related_publication': 1, 'id': 7, 'type': 'data_table'},
            {'related_publication': 1, 'id': 8, 'type': 'data_table'}]
    datatables, publications = splitter(docs, lambda d: 'related_publication' in d)

    assert (publications[0]['id'] == 1)
    assert (publications[0]['type'] == 'publication')
    assert (datatables[0]['type'] == 'data_table')
