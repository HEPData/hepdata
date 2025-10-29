import logging
import os
from unittest.mock import call

from datacite.errors import DataCiteUnauthorizedError, DataCiteError
from flask import render_template
from invenio_db import db
from invenio_pidstore.models import PersistentIdentifier
from invenio_pidstore.errors import PIDInvalidAction, PIDDoesNotExistError
import xmlschema
import pytest

from hepdata.modules.records.importer.api import import_records
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.doi_minter import get_or_create_doi, register_doi, \
    generate_doi_for_table, generate_dois_for_submission, \
    reserve_dois_for_data_submissions, reserve_doi_for_hepsubmission, \
    _get_submission_file_resources
from hepdata.modules.records.utils.submission import get_or_create_hepsubmission
from hepdata.modules.records.utils.workflow import create_record
from hepdata.modules.submission.models import DataSubmission, HEPSubmission, \
    License, DataResource


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


def test_get_or_create_doi(mock_data_cite_provider, caplog):
    caplog.set_level(logging.ERROR)

    # Valid call should just be passed to DataCiteProvider.
    # With no exceptions it assumes PID already exists so just calls get, not create
    get_or_create_doi('my.test.doi')
    mock_data_cite_provider.get.assert_called_once_with('my.test.doi', 'doi')
    mock_data_cite_provider.create.assert_not_called()

    # Mock a PIDDoesNotExistError so that create is called
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('doi', None)
    get_or_create_doi('my.test.doi')
    mock_data_cite_provider.get.assert_called_once_with('my.test.doi', 'doi')
    mock_data_cite_provider.create.assert_called_once_with('my.test.doi')

    # Exception on get or create should just log error
    caplog.clear()
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = Exception("Something went wrong")
    get_or_create_doi('my.test.doi')
    mock_data_cite_provider.get.assert_called_once_with('my.test.doi', 'doi')
    mock_data_cite_provider.create.assert_not_called()
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].msg == \
        "Unable to fetch DOI: Something went wrong"

    caplog.clear()
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('doi', None)
    mock_data_cite_provider.create.side_effect = Exception("Something else went wrong")
    get_or_create_doi('my.test.doi')
    mock_data_cite_provider.get.assert_called_once_with('my.test.doi', 'doi')
    mock_data_cite_provider.create.assert_called_once_with('my.test.doi')
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[0].msg == \
        "Unable to mint DOI: Something else went wrong"


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
    # Set data provider get to throw error so we are always creating new PIDs
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('doi', None)

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
        'http://localhost:5000/record/2'
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

    # Reset dois so we can check generate_dois...
    hep_submission.doi = None
    db.session.add(hep_submission)

    for data_submission in DataSubmission.query.filter_by(
            publication_inspire_id=hep_submission.inspire_id,
            version=hep_submission.version).all():
        data_submission.doi = None
        db.session.add(data_submission)

    for resource in _get_submission_file_resources(
            hep_submission.publication_recid, hep_submission.version,
            hep_submission):
        resource.doi = None
        db.session.add(resource)

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
    assert recid == 173
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

    # Set data provider get to throw error so we are always creating new PIDs
    mock_data_cite_provider.reset_mock()
    mock_data_cite_provider.get.side_effect = PIDDoesNotExistError('doi', None)

    # Generate DOIs again - should work and call `create` for record, v1, table
    generate_dois_for_submission(recid, recid)
    mock_data_cite_provider.create.assert_has_calls([
        call('10.17182/hepdata.173'),
        call('10.17182/hepdata.173.v1'),
        call('10.17182/hepdata.173.v1/t1')
    ])
    # Should have twice as many get calls as register calls (because get is called by create)
    assert mock_data_cite_provider.get.call_count == 6
    assert mock_data_cite_provider.create().register.call_count == 3


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
    datacite_schema = xmlschema.XMLSchema('http://schema.datacite.org/meta/kernel-4.4/metadata.xsd')

    # Get all versions for the publication
    all_versions = HEPSubmission.query.filter_by(
        publication_recid=hep_submission.publication_recid,
        overall_status='finished'
    ).order_by(HEPSubmission.version.asc()).all()
    
    base_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                               doi=hep_submission.doi,
                               overall_submission=hep_submission,
                               data_submissions=data_submissions,
                               resources=_get_submission_file_resources(hep_submission.publication_recid, hep_submission.version, hep_submission),
                               all_versions=all_versions,
                               publication_info=publication_info,
                               site_url=site_url)
    # Validate the base XML
    datacite_schema.validate(base_xml)

    version_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                                  doi=f"{hep_submission.doi}.v1",
                                  overall_submission=hep_submission,
                                  data_submissions=data_submissions,
                                  resources=_get_submission_file_resources(hep_submission.publication_recid, hep_submission.version, hep_submission),
                                  all_versions=all_versions,
                                  publication_info=publication_info,
                                  site_url=site_url)
    # Validate the version XML
    datacite_schema.validate(version_xml)

    for data_submission in data_submissions:
        data_xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                                   doi=data_submission.doi,
                                   table_name=data_submission.name,
                                   table_description=data_submission.description,
                                   overall_submission=hep_submission,
                                   data_submission=data_submission,
                                   publication_info=publication_info,
                                   site_url=site_url)
        # Validate the data submission XML
        datacite_schema.validate(data_xml)

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

        # Validate the resource XML
        datacite_schema.validate(resource_xml)


def test_get_submission_file_resources(app, identifiers):
    # Create data resources with random unordered ids, so they should be out
    # of order when fetched from the DB
    hep_submission = get_or_create_hepsubmission(1)
    for i in [1043, 1001, 1062, 1013, 1002]:
        resource = DataResource(id=i)
        if i == 1013: # Set one resource as remote so it won't be given a DOI
            resource.file_location = "https://github.com/hepdata"
        else:
            resource.file_location = "/a/b/c/d.txt"
        hep_submission.resources.append(resource)

    db.session.add(hep_submission)
    db.session.commit()

    file_resources = _get_submission_file_resources(hep_submission.publication_recid, 1)
    assert len(file_resources) == 4
    assert file_resources[0].id == 1001
    assert file_resources[1].id == 1002
    assert file_resources[2].id == 1043
    assert file_resources[3].id == 1062


def test_datacite_related_identifiers(app, identifiers):
    """Test that DataCite XML has correct relatedIdentifiers based on the issue requirements."""
    # Test data setup
    hep_submission = get_or_create_hepsubmission(1)
    data_submissions = DataSubmission.query.filter_by(
        publication_inspire_id=hep_submission.inspire_id,
        version=hep_submission.version) \
        .order_by(DataSubmission.id.asc()).all()
    resources = _get_submission_file_resources(hep_submission.publication_recid, hep_submission.version, hep_submission)
    publication_info = get_record_by_id(hep_submission.publication_recid)
    site_url = app.config.get('SITE_URL', 'https://www.hepdata.net')
    
    # Get all versions for the publication
    all_versions = HEPSubmission.query.filter_by(
        publication_recid=hep_submission.publication_recid,
        overall_status='finished'
    ).order_by(HEPSubmission.version.asc()).all()
    
    # Test unversioned whole record DOI
    base_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                               doi=hep_submission.doi,
                               overall_submission=hep_submission,
                               data_submissions=data_submissions,
                               resources=resources,
                               all_versions=all_versions,
                               publication_info=publication_info,
                               site_url=site_url)
    
    # Should contain versioned DOI with HasVersion relation for each version
    for version_submission in all_versions:
        expected_version_relation = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="HasVersion">{hep_submission.doi}.v{version_submission.version}</relatedIdentifier>'
        assert expected_version_relation in base_xml, f"Base XML should contain version relation: {expected_version_relation}"
    
    # Should NOT contain individual table DOIs in unversioned record
    for data_submission in data_submissions:
        assert data_submission.doi not in base_xml, f"Base XML should not contain table DOI: {data_submission.doi}"
    
    # Test versioned whole record DOI
    version_doi = f"{hep_submission.doi}.v{hep_submission.version}"
    version_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                                  doi=version_doi,
                                  overall_submission=hep_submission,
                                  data_submissions=data_submissions,
                                  resources=resources,
                                  all_versions=all_versions,
                                  publication_info=publication_info,
                                  site_url=site_url)
    
    # Should contain unversioned DOI with IsVersionOf relation
    expected_unversioned_relation = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="IsVersionOf">{hep_submission.doi}</relatedIdentifier>'
    assert expected_unversioned_relation in version_xml, f"Version XML should contain unversioned relation: {expected_unversioned_relation}"
    
    # Should contain individual table DOIs with HasPart relation
    for data_submission in data_submissions:
        expected_table_relation = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Dataset" relationType="HasPart">{data_submission.doi}</relatedIdentifier>'
        assert expected_table_relation in version_xml, f"Version XML should contain table relation: {expected_table_relation}"
    
    # Should contain resource DOIs with HasPart relation (if any)
    for resource in resources:
        if resource.doi:
            expected_resource_relation = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Other" relationType="HasPart">{resource.doi}</relatedIdentifier>'
            assert expected_resource_relation in version_xml, f"Version XML should contain resource relation: {expected_resource_relation}"
    
    # Test individual table DOI
    if data_submissions:
        data_submission = data_submissions[0]
        table_xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                                    doi=data_submission.doi,
                                    table_name=data_submission.name,
                                    table_description=data_submission.description,
                                    overall_submission=hep_submission,
                                    data_submission=data_submission,
                                    publication_info=publication_info,
                                    site_url=site_url)
        
        # Should reference versioned whole record DOI, not unversioned
        expected_versioned_container = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="IsPartOf">{hep_submission.doi}.v{hep_submission.version}</relatedIdentifier>'
        assert expected_versioned_container in table_xml, f"Table XML should reference versioned container: {expected_versioned_container}"
        
        # Should NOT reference unversioned DOI
        unexpected_unversioned_container = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="IsPartOf">{hep_submission.doi}</relatedIdentifier>'
        assert unexpected_unversioned_container not in table_xml, f"Table XML should not reference unversioned container: {unexpected_unversioned_container}"
    
    # Test resource file DOI
    if resources and any(r.doi for r in resources):
        resource = next(r for r in resources if r.doi)
        license = None
        if resource.file_license:
            license = License.query.filter_by(id=resource.file_license).first()
            
        resource_xml = render_template('hepdata_records/formats/datacite/datacite_resource.xml',
                                       resource=resource,
                                       doi=resource.doi,
                                       overall_submission=hep_submission,
                                       filename=os.path.basename(resource.file_location),
                                       license=license,
                                       publication_info=publication_info,
                                       site_url=site_url)
        
        # Should reference versioned whole record DOI, not unversioned
        expected_versioned_container = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="IsPartOf">{hep_submission.doi}.v{hep_submission.version}</relatedIdentifier>'
        assert expected_versioned_container in resource_xml, f"Resource XML should reference versioned container: {expected_versioned_container}"
        
        # Should NOT reference unversioned DOI
        unexpected_unversioned_container = f'<relatedIdentifier relatedIdentifierType="DOI" resourceTypeGeneral="Collection" relationType="IsPartOf">{hep_submission.doi}</relatedIdentifier>'
        assert unexpected_unversioned_container not in resource_xml, f"Resource XML should not reference unversioned container: {unexpected_unversioned_container}"
