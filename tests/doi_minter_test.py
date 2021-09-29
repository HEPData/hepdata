import logging
from unittest.mock import call

from datacite.errors import DataCiteUnauthorizedError, DataCiteError
from flask import render_template
from invenio_db import db
from invenio_pidstore.errors import PIDInvalidAction, PIDDoesNotExistError
import lxml
import pytest

from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.doi_minter import create_doi, register_doi, \
    generate_doi_for_table, generate_dois_for_submission
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.models import DataSubmission


@pytest.fixture()
def mock_data_cite_provider(app, mocker, load_default_data):
    """Mock DataCiteProvider and temporarily disable NO_DOI_MINTING

    This enables us to check that register_doi makes hte appropriate calls to
    DataCiteProvider without making requests to DataCite

    load_default_data is used here so it is loaded before we change the settings
    """
    mock_data_cite_provider = mocker.patch('hepdata.modules.records.utils.doi_minter.DataCiteProvider')
    no_doi_minting_config = app.config.get('NO_DOI_MINTING')
    app.config['NO_DOI_MINTING'] = False

    yield mock_data_cite_provider

    if no_doi_minting_config:
        app.config['NO_DOI_MINTING'] = True


def test_create_doi(mock_data_cite_provider, caplog):
    caplog.set_level(logging.ERROR)

    # Valid call should just be passed to DataCiteProvider
    create_doi('my.test.doi')
    mock_data_cite_provider.create.assert_called_once_with('my.test.doi')

    # Unauthorised exception should log error
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.create.side_effect = DataCiteUnauthorizedError()
    create_doi('my.test.doi')
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].msg == \
        "Unable to mint DOI. No authorisation credentials provided."

    # Any other exception should call get instead
    caplog.clear()
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.create.side_effect = Exception()
    create_doi('my.test.doi')
    mock_data_cite_provider.create.assert_called_once_with('my.test.doi')
    mock_data_cite_provider.get.assert_called_once_with('my.test.doi', 'doi')


def test_register_doi(mock_data_cite_provider, caplog):
    caplog.set_level(logging.ERROR)

    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
    mock_data_cite_provider.assert_has_calls([
        call.get('my.test.doi', 'doi'),
        call.get().register('http://localhost:5000', '<xml>')
    ])

    # Invalid PID exception should call create before continuing
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('mytype', 'myvalue')
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
    mock_data_cite_provider.assert_has_calls([
        call.get('my.test.doi', 'doi'),
        call.create('my.test.doi'),
        call.create().register('http://localhost:5000', '<xml>')
    ])

    # Unauthorised exception should log error
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = None
    mock_data_cite_provider.get().register.side_effect = DataCiteUnauthorizedError()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].msg == \
        "Unable to mint DOI. No authorisation credentials provided."

    # PIDInvalidAction should cause retry via update method
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get().register.side_effect = PIDInvalidAction()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
    mock_data_cite_provider.get().update.assert_called_once_with('http://localhost:5000', '<xml>')

    # DataCiteError should cause retry via register method
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get().register.side_effect = DataCiteError()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'uuid')
    mock_data_cite_provider.get().register.assert_has_calls([
        call('http://localhost:5000', '<xml>'),
        call('http://localhost:5000', '<xml>')
    ])



def test_generate_doi_for_table(mock_data_cite_provider, identifiers, capsys):
    # Valid doi
    doi = '10.17182/hepdata.1.v1/t1'
    generate_doi_for_table(doi)
    mock_data_cite_provider.get.assert_called_with(doi, 'doi')
    mock_data_cite_provider.get().register.assert_called()

    # Invalid doi
    capsys.readouterr()
    invalid_doi = 'thisisnotadoi'
    generate_doi_for_table(invalid_doi)
    out, err = capsys.readouterr()
    assert out.strip() == "Table DOI thisisnotadoi not found in database"

    # Table without finished submission
    hep_submission = get_or_create_hepsubmission(1)
    hep_submission.overall_status = 'todo'
    db.session.add(hep_submission)
    db.session.commit()

    generate_doi_for_table(doi)
    out, err = capsys.readouterr()
    assert out.strip() == f"Finished submission with INSPIRE ID {identifiers[0]['inspire_id']} and version 1 not found in database"


def test_generate_dois_for_submission(mock_data_cite_provider, identifiers):
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

    # Call again, passing publication_recids
    mock_data_cite_provider.reset_mock()
    generate_dois_for_submission(16, 16)
    # Should have registered DOIs for identifiers[1]
    # register_doi is called twice for the submission and once for each table
    total_calls = identifiers[1]['data_tables'] + 2

    # get is called first on the DataCiteProvider
    assert mock_data_cite_provider.get.call_count == total_calls
    get_call_args = mock_data_cite_provider.get.call_args_list
    assert call('10.17182/hepdata.16', 'doi') in get_call_args
    assert call('10.17182/hepdata.16.v1', 'doi') in get_call_args
    for i in range(identifiers[1]['data_tables']):
        assert call(f'10.17182/hepdata.16.v1/t{i+1}', 'doi') in get_call_args

    # Check no calls are made if we try to register DOI for unfinished submission
    mock_data_cite_provider.reset_mock()
    record_information = create_record({})
    recid = record_information['recid']
    assert recid == 57
    hep_submission = get_or_create_hepsubmission(recid)
    generate_dois_for_submission(recid, recid)
    mock_data_cite_provider.assert_not_called()

    # Create a data submission and set hep_submission status to finished
    hep_submission.inspire_id = '999999'
    hep_submission.overall_status = 'finished'
    db.session.add(hep_submission)
    data_submission = DataSubmission(
        publication_recid=recid,
        associated_recid=1,
        version=1,
        publication_inspire_id=hep_submission.inspire_id,
        name="mytable",
        description="mydescription"
    )
    db.session.add(data_submission)
    db.session.commit()

    # Generate DOIs again - should work and call `create` for record, v1, table
    generate_dois_for_submission(recid, recid)
    mock_data_cite_provider.create.assert_has_calls([
        call('10.17182/hepdata.57'),
        call('10.17182/hepdata.57.v1'),
        call('10.17182/hepdata.57.v1/t1')
    ])
    # Should also have same number of get and register calls
    assert mock_data_cite_provider.get.call_count == 3
    assert mock_data_cite_provider.get().register.call_count == 3


def test_xml_validates(app, identifiers):
    # Test that the XML produced validates against the datacite schema
    hep_submission = get_or_create_hepsubmission(1)
    data_submissions = DataSubmission.query.filter_by(
        publication_inspire_id=hep_submission.inspire_id,
        version=hep_submission.version) \
        .order_by(DataSubmission.id.asc()).all()
    publication_info = get_record_by_id(hep_submission.publication_recid)
    site_url = app.config.get('SITE_URL', 'https://www.hepdata.net')

    # Load schema
    datacite_schema = schema = lxml.etree.XMLSchema(file = 'http://schema.datacite.org/meta/kernel-4.4/metadata.xsd')

    base_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                               doi=hep_submission.doi,
                               overall_submission=hep_submission,
                               data_submissions=data_submissions,
                               publication_info=publication_info,
                               site_url=site_url)
    base_doc = lxml.etree.fromstring(base_xml)
    datacite_schema.assertValid(base_doc)

    version_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                                  doi=f"{hep_submission.doi}.v1",
                                  overall_submission=hep_submission,
                                  data_submissions=data_submissions,
                                  publication_info=publication_info,
                                  site_url=site_url)
    version_doc = lxml.etree.fromstring(version_xml)
    datacite_schema.assertValid(version_doc)

    for data_submission in data_submissions:
        data_xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                                   doi=data_submission.doi,
                                   table_name=data_submission.name,
                                   table_description=data_submission.description,
                                   overall_submission=hep_submission,
                                   data_submission=data_submission,
                                   license=license,
                                   publication_info=publication_info,
                                   site_url=site_url)
        data_doc = lxml.etree.fromstring(data_xml)
        datacite_schema.assertValid(data_doc)
