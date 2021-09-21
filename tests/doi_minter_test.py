from unittest.mock import call

from hepdata.modules.records.utils.doi_minter import register_doi, generate_dois_for_submission


def test_register_doi(app, mocker):
    mock_data_cite_provider = mocker.patch('hepdata.modules.records.utils.doi_minter.DataCiteProvider')
    no_doi_minting_config = app.config.get('NO_DOI_MINTING')
    app.config['NO_DOI_MINTING'] = False

    try:
        register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
        mock_data_cite_provider.assert_has_calls([
            call.get('my.test.doi', 'doi'),
            call.get().register('http://localhost:5000', '<xml>')
        ])
    finally:
        if no_doi_minting_config:
            app.config['NO_DOI_MINTING'] = True


def test_generate_dois_for_submission(app, mocker, load_default_data, identifiers):
    mock_data_cite_provider = mocker.patch('hepdata.modules.records.utils.doi_minter.DataCiteProvider')
    no_doi_minting_config = app.config.get('NO_DOI_MINTING')
    app.config['NO_DOI_MINTING'] = False

    try:
        generate_dois_for_submission(inspire_id=identifiers[0]['inspire_id'])
        # register_doi is called twice for the submission and once for each table
        total_calls = identifiers[0]['data_tables'] + 2

        # get is called first on the DataCiteProvider
        assert mock_data_cite_provider.get.call_count == total_calls
        get_call_args = mock_data_cite_provider.get.call_args_list
        assert call('10.17182/hepdata.1', 'doi') in get_call_args
        assert call('10.17182/hepdata.1.v1', 'doi') in get_call_args
        for i in range(identifiers[0]['data_tables']):
            assert call(f'10.17182/hepdata.1.v1/t{i+1}', 'doi') in get_call_args

        # get.register is called with the same dois (but with xml which we won't check)
        assert mock_data_cite_provider.get().register.call_count == total_calls
    finally:
        if no_doi_minting_config:
            app.config['NO_DOI_MINTING'] = True
