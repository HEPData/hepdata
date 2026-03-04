import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, request
from hepdata.modules.records.views import get_metadata_by_alternative_id


class TestGetMetadataByAlternativeId:
    """Test cases for get_metadata_by_alternative_id function."""

    def test_valid_inspire_id_success(self, app):
        """Test successful retrieval with valid inspire ID format."""
        with app.test_request_context('/record/ins12345?version=1&format=json'):
            # Mock the database search to return a valid record
            mock_record = {
                'recid': 1,
                'inspire_id': 12345,
                'title': 'Test Record'
            }
            mock_search_result = {
                'hits': {
                    'hits': [{'_source': mock_record}]
                }
            }

            with patch('hepdata.modules.records.views.get_records_matching_field') as mock_search, \
                 patch('hepdata.modules.records.views.render_record') as mock_render, \
                 patch('hepdata.modules.records.views.should_send_json_ld') as mock_json_ld:

                mock_search.return_value = mock_search_result
                mock_json_ld.return_value = False
                mock_render.return_value = 'rendered_record'

                result = get_metadata_by_alternative_id('ins12345')

                # Verify the inspire_id was extracted correctly
                mock_search.assert_called_once_with('inspire_id', 12345, doc_type='publication')

                # Verify render_record was called with correct parameters
                mock_render.assert_called_once_with(
                    recid=1,
                    record=mock_record,
                    version=1,
                    output_format='json',
                    light_mode=False,
                    observer_key=None
                )

                assert result == 'rendered_record'

    def test_invalid_inspire_id_format_non_numeric(self, app):
        """Test handling of invalid inspire ID format with non-numeric part."""
        with app.test_request_context('/record/ins_abc'):
            with patch('hepdata.modules.records.views.log') as mock_log, \
                 patch('hepdata.modules.records.views.abort') as mock_abort:

                mock_abort.return_value = 'aborted_404'

                result = get_metadata_by_alternative_id('ins_abc')

                # Verify warning was logged
                mock_log.warning.assert_called()
                assert "invalid literal for int() with base 10: '_abc'" in str(mock_log.warning.call_args[0])

                # Verify abort(404) was called
                mock_abort.assert_called_once_with(404)
                assert result == 'aborted_404'

    def test_invalid_inspire_id_format_no_ins_prefix(self, app):
        """Test handling of invalid inspire ID format without 'ins' prefix."""
        with app.test_request_context('/record/i12345'):
            with patch('hepdata.modules.records.views.log') as mock_log, \
                 patch('hepdata.modules.records.views.abort') as mock_abort:

                mock_abort.return_value = 'aborted_404'

                result = get_metadata_by_alternative_id('i12345')

                # Verify warning was logged
                mock_log.warning.assert_called()
                assert "invalid literal for int() with base 10: 'i12345'" in str(mock_log.warning.call_args[0])

                # Verify abort(404) was called
                mock_abort.assert_called_once_with(404)
                assert result == 'aborted_404'

    def test_record_not_found(self, app):
        """Test handling when no record is found for valid inspire ID."""
        with app.test_request_context('/record/ins99999'):
            # Mock empty search results
            mock_search_result = {
                'hits': {
                    'hits': []
                }
            }

            with patch('hepdata.modules.records.views.get_records_matching_field') as mock_search, \
                 patch('hepdata.modules.records.views.log') as mock_log, \
                 patch('hepdata.modules.records.views.abort') as mock_abort:

                mock_search.return_value = mock_search_result
                mock_abort.return_value = 'aborted_404'

                result = get_metadata_by_alternative_id('ins99999')

                # Verify search was attempted
                mock_search.assert_called_once_with('inspire_id', 99999, doc_type='publication')

                # Verify warning was logged when no records are found
                mock_log.warning.assert_called()

                # Verify abort(404) was called
                mock_abort.assert_called_once_with(404)
                assert result == 'aborted_404'

    def test_json_ld_format_detection(self, app):
        """Test JSON-LD format detection based on Accept header."""
        with app.test_request_context('/record/ins12345', headers={'Accept': 'application/ld+json'}):
            mock_record = {'recid': 1, 'inspire_id': 12345}
            mock_search_result = {'hits': {'hits': [{'_source': mock_record}]}}

            with patch('hepdata.modules.records.views.get_records_matching_field') as mock_search, \
                 patch('hepdata.modules.records.views.render_record') as mock_render, \
                 patch('hepdata.modules.records.views.should_send_json_ld') as mock_json_ld:

                mock_search.return_value = mock_search_result
                mock_json_ld.return_value = True
                mock_render.return_value = 'json_ld_record'

                result = get_metadata_by_alternative_id('ins12345')

                # Verify JSON-LD format was used
                mock_render.assert_called_once_with(
                    recid=1,
                    record=mock_record,
                    version=-1,
                    output_format='json_ld',
                    light_mode=False,
                    observer_key=None
                )


# Testing Metadata by recid
def test_metadata_by_id_record_failure(app, client):
    """
        Test handling of metadata by recid record retrieval function failure.
        Tests case where record and version are not provided.

    """
    test_id = 1
    with patch('hepdata.modules.records.views.get_record_contents') as mock_get_record_contents, \
         patch('hepdata.modules.records.views.render_record') as mock_render:

        # Make get_record_contents raise an Exception to set record to None
        mock_get_record_contents.side_effect = Exception('Test Exception')
        mock_render.return_value = 'test_render'

        # Request record with invalid version
        _response = client.get(f'/record/{test_id}?version=not-an-int&format=json')

        # We want to ensure that render_record is called with record=None and version=-1
        mock_render.assert_called_once_with(
            recid=test_id,
            record=None, # Set by exception handler
            version=-1, # Set by exception handler
            output_format='json',
            light_mode=False,
            observer_key=None
        )


def test_get_table_details_version_access_control(app, client):
    """
    Test that get_table_details returns 403 when a user without permissions
    tries to access an unpublished version (version_count < version_count_all
    and version == version_count_all).
    """
    recid = 1
    data_recid = 1
    version = 2  # Trying to access version 2 (unpublished)

    with patch('hepdata.modules.records.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.records.views.get_version_count') as mock_version_count:

        mock_verify.return_value = False  # Key not verified
        # User can only see 1 version (finished), but there are 2 total
        mock_version_count.return_value = (1, 2)

        response = client.get(f'/record/data/{recid}/{data_recid}/{version}/')
        assert response.status_code == 403


def test_get_resource_not_found(app, client):
    """
    Test that get_resource returns 404 when the resource does not exist.
    """
    response = client.get('/record/resource/99999999')
    assert response.status_code == 404


def test_get_resource_no_publication(app, client):
    """
    Test that get_resource returns 404 when there is no associated
    HEPSubmission or DataSubmission for the resource.
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    # Create a DataResource not linked to any submission
    orphan_resource = DataResource(
        file_location='http://example.com/orphan.txt',
        file_type='url',
        file_description='Orphan resource'
    )
    db.session.add(orphan_resource)
    db.session.commit()

    with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
         patch('hepdata.modules.records.views.DataSubmission.query') as mock_data_query:
        mock_hep_query.filter.return_value.first.return_value = None
        mock_data_query.filter.return_value.first.return_value = None

        response = client.get(f'/record/resource/{orphan_resource.id}')
        assert response.status_code == 404

    # Cleanup
    db.session.delete(orphan_resource)
    db.session.commit()


def test_get_resource_observer_key_in_location(app, client):
    """
    Test that get_resource includes observer_key in the returned location
    when the key is verified (covers the key_verified path in the else branch).
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource, HEPSubmission, SubmissionObserver

    # Create test data
    resource = DataResource(
        file_location='http://example.com/file.txt',
        file_type='url',
        file_description='Test resource'
    )
    db.session.add(resource)
    db.session.flush()

    submission = HEPSubmission(publication_recid=88881, coordinator=1,
                               overall_status='finished', version=1)
    db.session.add(submission)
    db.session.flush()

    observer = SubmissionObserver(88881)
    db.session.add(observer)
    db.session.commit()

    observer_key = observer.observer_key

    with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
         patch('hepdata.modules.records.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.records.views.get_version_count') as mock_version_count:

        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 88881
        mock_hep_sub.version = 1
        mock_hep_query.filter.return_value.first.return_value = mock_hep_sub
        mock_verify.return_value = True  # Key verified
        mock_version_count.return_value = (1, 1)

        response = client.get(
            f'/record/resource/{resource.id}?observer_key={observer_key}',
            headers={'Accept': 'application/json'}
        )
        # Should be 200 and include observer_key in location
        assert response.status_code == 200
        data = json.loads(response.data)
        assert f'observer_key={observer_key}' in data['location']

    # Cleanup
    db.session.delete(observer)
    db.session.delete(submission)
    db.session.delete(resource)
    db.session.commit()


def test_get_resource_version_access_control(app, client):
    """
    Test that get_resource returns 403 when a user without permissions
    tries to access an unpublished version via a resource.
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    resource = DataResource(
        file_location='http://example.com/test.txt',
        file_type='url',
        file_description='Test resource'
    )
    db.session.add(resource)
    db.session.commit()

    with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
         patch('hepdata.modules.records.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.records.views.get_version_count') as mock_version_count:

        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 77771
        mock_hep_sub.version = 2  # Latest (unpublished) version
        mock_hep_query.filter.return_value.first.return_value = mock_hep_sub
        mock_verify.return_value = False  # Key not verified
        # User can see 1 version (finished), but there are 2 total
        mock_version_count.return_value = (1, 2)

        response = client.get(f'/record/resource/{resource.id}')
        assert response.status_code == 403

    # Cleanup
    db.session.delete(resource)
    db.session.commit()
