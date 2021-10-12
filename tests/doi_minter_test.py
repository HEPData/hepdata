import logging
import os
from unittest.mock import call

from datacite.errors import DataCiteUnauthorizedError, DataCiteError
from flask import render_template
from invenio_db import db
from invenio_pidstore.models import PersistentIdentifier
from invenio_pidstore.errors import PIDInvalidAction, PIDDoesNotExistError
import lxml
import pytest

from hepdata.modules.records.importer.api import import_records
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.doi_minter import create_doi, register_doi, \
    generate_doi_for_table, generate_dois_for_submission, \
    reserve_dois_for_data_submissions, reserve_doi_for_hepsubmission
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.models import DataSubmission, HEPSubmission, License


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

    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', 'notarealuuid')
    mock_data_cite_provider.assert_has_calls([
        call.get('my.test.doi', 'doi'),
        call.get().register('http://localhost:5000', '<xml>')
    ])

    # Create a PidstoreIdentifier object with the doi, then try again - should
    # update pidstore obj with new uuid
    pidstore_obj = PersistentIdentifier.create(pid_type='doi', pid_value='my.test.doi')
    db.session.add(pidstore_obj)
    db.session.commit()
    assert pidstore_obj.object_uuid is None

    publication_info = get_record_by_id(1)
    mock_data_cite_provider.reset_mock()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', publication_info['uuid'])
    mock_data_cite_provider.assert_has_calls([
        call.get('my.test.doi', 'doi'),
        call.get().register('http://localhost:5000', '<xml>')
    ])
    assert str(pidstore_obj.object_uuid) == publication_info['uuid']

    # Invalid PID exception should call create before continuing
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('mytype', 'myvalue')
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', publication_info['uuid'])
    mock_data_cite_provider.assert_has_calls([
        call.get('my.test.doi', 'doi'),
        call.create('my.test.doi'),
        call.create().register('http://localhost:5000', '<xml>')
    ])

    # Unauthorised exception should log error
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = None
    mock_data_cite_provider.get().register.side_effect = DataCiteUnauthorizedError()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', publication_info['uuid'])
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].msg == \
        "Unable to mint DOI. No authorisation credentials provided."

    # PIDInvalidAction should cause retry via update method
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get().register.side_effect = PIDInvalidAction()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', publication_info['uuid'])
    mock_data_cite_provider.get().update.assert_called_once_with('http://localhost:5000', '<xml>')

    # DataCiteError should cause retry via register method
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get().register.side_effect = DataCiteError()
    register_doi('my.test.doi', 'http://localhost:5000', '<xml>', publication_info['uuid'])
    mock_data_cite_provider.get().register.assert_has_calls([
        call('http://localhost:5000', '<xml>'),
        call('http://localhost:5000', '<xml>')
    ])


def test_reserve_doi_for_hepsubmission(mock_data_cite_provider, identifiers):
    # Unset DOI on submission, and set version to 0 (to make sure it's bumped
    # to 1 in the DOI)
    hep_submission = get_or_create_hepsubmission(1)
    hep_submission.doi = None
    hep_submission.version = 0
    db.session.add(hep_submission)
    db.session.commit()

    # Check appropriate DOI has been created
    reserve_doi_for_hepsubmission(hep_submission)
    base_doi = '10.17182/hepdata.1'
    version_doi = '10.17182/hepdata.1.v1'
    mock_data_cite_provider.create.call_args == [
        call(base_doi),
        call(version_doi)
    ]
    # Check that doi has been updated on submission
    assert hep_submission.doi == base_doi

    # Check that no calls were made to the DataCiteProvider's API
    mock_data_cite_provider.api.assert_not_called()


def test_reserve_dois_for_data_submissions(mock_data_cite_provider, identifiers):
    # Unset DOIs on data submissions
    data_submissions = DataSubmission.query.filter_by(
        publication_inspire_id=identifiers[0]['inspire_id'],
        version=1) \
        .order_by(DataSubmission.id.asc()).all()

    for data_submission in data_submissions:
        data_submission.doi = None
        db.session.add(data_submission)

    # Set version to 0 for first submission - should still use v1 in the DOI
    data_submissions[0].version = 0

    db.session.commit()

    # Check appropriate DOIs are reserved
    reserve_dois_for_data_submissions(publication_recid=1)
    assert mock_data_cite_provider.create.call_count == identifiers[0]['data_tables']
    create_call_args = mock_data_cite_provider.create.call_args_list

    # Check doi has been created on datacite, and also set in the DB
    for i in range(identifiers[0]['data_tables']):
        doi = f'10.17182/hepdata.1.v1/t{i+1}'
        assert call(doi) in create_call_args
        assert data_submissions[i].doi == doi

    # Check that no calls were made to the DataCiteProvider's API
    mock_data_cite_provider.api.assert_not_called()

    # Test passing invalid arguments raises a KeyError
    with pytest.raises(KeyError) as excinfo:
        reserve_dois_for_data_submissions()
    assert 'No inspire_id or data_submissions parameter provided' in str(excinfo.value)


def test_generate_doi_for_table(mock_data_cite_provider, identifiers, capsys):
    # Valid doi
    doi = '10.17182/hepdata.1.v1/t1'
    generate_doi_for_table(doi)
    mock_data_cite_provider.get.assert_called_with(doi, 'doi')
    mock_data_cite_provider.get().register.assert_called()
    assert mock_data_cite_provider.get().register.call_args[0][0] == \
        'http://localhost:5000/record/ins1283842?version=1&table=Table 1'
    assert '<creatorName nameType="Organizational">D0 Collaboration</creatorName>' in \
        mock_data_cite_provider.get().register.call_args[0][1]

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

    # get.register is called with the same dois
    assert mock_data_cite_provider.get().register.call_count == total_calls
    # Check first calls (for submission) have collaboration info in XML
    assert '<creatorName nameType="Organizational">D0 Collaboration</creatorName>' in \
        mock_data_cite_provider.get().register.call_args_list[0][0][1]
    assert '<creatorName nameType="Organizational">D0 Collaboration</creatorName>' in \
        mock_data_cite_provider.get().register.call_args_list[1][0][1]

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

    # Import a submission with resources and check we also create resource DOIs
    import_records(['ins1748602'], synchronous=True)
    hep_submission = get_or_create_hepsubmission(57)

    # Reset doi so we can check generate_dois...
    hep_submission.doi = None
    db.session.add(hep_submission)
    db.session.commit()

    mock_data_cite_provider.reset_mock()
    generate_dois_for_submission(57, 57)
    get_call_args = mock_data_cite_provider.get.call_args_list
    assert call('10.17182/hepdata.57', 'doi') in get_call_args
    assert call('10.17182/hepdata.57.v1', 'doi') in get_call_args
    for i in range(48):
        assert call(f'10.17182/hepdata.57.v1/t{i+1}', 'doi') in get_call_args
    for i in range(3):
        assert call(f'10.17182/hepdata.57.v1/r{i+1}', 'doi') in get_call_args

    # Check no calls are made if we try to register DOI for unfinished submission
    mock_data_cite_provider.reset_mock()
    record_information = create_record({})
    recid = record_information['recid']
    assert recid == 106
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
        call('10.17182/hepdata.106'),
        call('10.17182/hepdata.106.v1'),
        call('10.17182/hepdata.106.v1/t1')
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
    datacite_schema = lxml.etree.XMLSchema(file = 'http://schema.datacite.org/meta/kernel-4.4/metadata.xsd')

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
                                   publication_info=publication_info,
                                   site_url=site_url)
        data_doc = lxml.etree.fromstring(data_xml)
        datacite_schema.assertValid(data_doc)

    # Import a record with a resource file
    import_records(['ins1748602'], synchronous=True)
    hep_submission = HEPSubmission.query.filter_by(
        inspire_id='1748602'
    ).first()
    publication_info = get_record_by_id(hep_submission.publication_recid)

    for i, resource in enumerate(hep_submission.resources):
        license = None
        if resource.file_license:
            license = License.query.filter_by(id=resource.file_license).first()

        resource_xml = render_template(
            'hepdata_records/formats/datacite/datacite_resource.xml',
            resource=resource,
            doi=resource.doi,
            overall_submission=hep_submission,
            filename=os.path.basename(resource.file_location),
            license=license,
            publication_info=publication_info,
            site_url=site_url)

        print(resource_xml)

        doc = lxml.etree.fromstring(resource_xml)
        datacite_schema.assertValid(doc)
