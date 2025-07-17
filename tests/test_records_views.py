import pytest
from unittest.mock import Mock, patch
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
                    light_mode=False
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
                assert 'Unable to find ins_abc' in str(mock_log.warning.call_args[0])
                
                # Verify abort(404) was called
                mock_abort.assert_called_once_with(404)
                assert result == 'aborted_404'

    def test_invalid_inspire_id_format_no_ins_prefix(self, app):
        """Test handling of invalid inspire ID format without 'ins' prefix."""
        with app.test_request_context('/record/12345'):
            with patch('hepdata.modules.records.views.log') as mock_log, \
                 patch('hepdata.modules.records.views.abort') as mock_abort:
                
                mock_abort.return_value = 'aborted_404'
                
                result = get_metadata_by_alternative_id('12345')
                
                # Verify warning was logged
                mock_log.warning.assert_called()
                assert 'Unable to find 12345' in str(mock_log.warning.call_args[0])
                
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
                
                # Verify warning was logged (IndexError causes exception handling)
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
                    light_mode=False
                )
