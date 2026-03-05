import json
import os
import tempfile
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


def test_get_table_details_version_zero_fallback(app, client):
    """
    Test that get_table_details sets version to version_count when version=0.
    Covers line 325: version = version_count if version_count else 1.
    """
    recid = 1
    data_recid = 1

    mock_datasub_record = MagicMock()
    mock_datasub_record.data_file = 1
    mock_datasub_record.name = 'Table 1'
    mock_datasub_record.description = 'Test'
    mock_datasub_record.keywords = []
    mock_datasub_record.doi = None
    mock_datasub_record.location_in_publication = None
    mock_datasub_record.resources = []

    mock_datasub_query = MagicMock()
    mock_datasub_query.count.return_value = 1
    mock_datasub_query.one.return_value = mock_datasub_record

    mock_data_record = MagicMock()
    mock_data_record.file_location = '/fake/path.json'
    mock_data_record.file_license = None

    mock_data_query = MagicMock()
    mock_data_query.count.return_value = 1
    mock_data_query.one.return_value = mock_data_record

    with patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
         patch('hepdata.modules.records.views.get_version_count', return_value=(2, 2)), \
         patch('hepdata.modules.records.views.DataSubmission') as mock_ds, \
         patch('hepdata.modules.records.views.db') as mock_db, \
         patch('hepdata.modules.records.views.file_size_check', return_value={'status': True, 'size': 0}), \
         patch('hepdata.modules.records.views.generate_license_data_by_id', return_value={}), \
         patch('hepdata.modules.records.views.get_table_data_list', return_value=[]), \
         patch('hepdata.modules.records.views.get_resource_data', return_value=[]), \
         patch('hepdata.modules.records.views.create_data_review', return_value=None), \
         patch('hepdata.modules.records.views.generate_table_headers', return_value={}), \
         patch('hepdata.modules.records.views.generate_table_data', return_value={}), \
         patch('hepdata.modules.records.views.load_table_data', return_value=None):

        mock_ds.query.options.return_value.filter_by.return_value = mock_datasub_query
        mock_db.session.query.return_value.filter.return_value = mock_data_query

        # version=0 triggers "if not version:" fallback → sets version to version_count (2)
        response = client.get(f'/record/data/{recid}/{data_recid}/0/')
        assert response.status_code == 200


def test_get_resource_tar_file_binary_content(app, client):
    """
    Test that get_resource sets contents='Binary' for tar files.
    Covers line 813: contents = 'Binary' (when mimetype is application/x-tar).
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    # Create temp .tar file with readable text content
    with tempfile.NamedTemporaryFile(suffix='.tar', delete=False, mode='w') as f:
        f.write('sample tar content')
        tar_path = f.name

    try:
        resource = DataResource(
            file_location=tar_path,
            file_type='data',
            file_description='Test tar resource'
        )
        db.session.add(resource)
        db.session.commit()

        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55551
        mock_hep_sub.version = 1

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)), \
             patch('hepdata.modules.records.views.mimetypes.guess_type',
                   return_value=('application/x-tar', None)):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            response = client.get(f'/record/resource/{resource.id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            # tar files should have contents set to 'Binary'
            assert data['file_contents'] == 'Binary'
    finally:
        os.unlink(tar_path)
        db.session.delete(resource)
        db.session.commit()


def test_get_resource_unicode_decode_error(app, client):
    """
    Test that get_resource handles UnicodeDecodeError when reading a file.
    Covers lines 814-815: except UnicodeDecodeError: contents = 'Binary'.
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    # Create temp file with non-UTF-8 binary content
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False, mode='wb') as f:
        f.write(b'\x80\x81\x82\x83')  # Not valid UTF-8
        bin_path = f.name

    try:
        resource = DataResource(
            file_location=bin_path,
            file_type='data',
            file_description='Test binary resource'
        )
        db.session.add(resource)
        db.session.commit()

        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55552
        mock_hep_sub.version = 1

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)), \
             patch('hepdata.modules.records.views.mimetypes.guess_type',
                   return_value=('application/octet-stream', None)):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            response = client.get(f'/record/resource/{resource.id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            # UnicodeDecodeError should result in contents being set to 'Binary'
            assert data['file_contents'] == 'Binary'
    finally:
        os.unlink(bin_path)
        db.session.delete(resource)
        db.session.commit()


def test_get_resource_view_mode_http_redirect(app, client):
    """
    Test that get_resource redirects to an HTTP URL when ?view=true is set.
    Covers line 843: return redirect(resource_obj.file_location).
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    resource = DataResource(
        file_location='http://example.com/view_redirect_file.txt',
        file_type='url',
        file_description='Test HTTP view resource'
    )
    db.session.add(resource)
    db.session.commit()

    try:
        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55553
        mock_hep_sub.version = 1

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            # ?view=true sets view_mode=True; HTTP URL should trigger redirect
            response = client.get(
                f'/record/resource/{resource.id}?view=true',
                follow_redirects=False
            )
            assert response.status_code == 302
            assert 'http://example.com/view_redirect_file.txt' in response.headers['Location']
    finally:
        db.session.delete(resource)
        db.session.commit()


def test_get_resource_local_html_file(app, client):
    """
    Test that get_resource returns file contents for a local HTML file.
    Covers lines 848-849: with open(...) as resource_file: return contents.
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    # Create a real temp HTML file so open() succeeds on both calls
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
        f.write('<html><body>Local HTML Content</body></html>')
        html_path = f.name

    try:
        resource = DataResource(
            file_location=html_path,
            file_type='html',
            file_description='Test local HTML resource'
        )
        db.session.add(resource)
        db.session.commit()

        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55554
        mock_hep_sub.version = 1

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            # Without ?view=true or ?landing_page=true, local HTML file returns contents directly
            response = client.get(f'/record/resource/{resource.id}')
            assert response.status_code == 200
            assert b'Local HTML Content' in response.data
    finally:
        os.unlink(html_path)
        db.session.delete(resource)
        db.session.commit()


def test_get_resource_landing_page_observer_key(app, client):
    """
    Test that get_resource appends observer_key to content_url and sets it on ctx
    when key is verified and landing_page=true.
    Covers lines 855 and 858.
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    resource = DataResource(
        file_location='http://example.com/landing_page_resource.txt',
        file_type='url',
        file_description='Test landing page resource'
    )
    db.session.add(resource)
    db.session.commit()

    try:
        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55555
        mock_hep_sub.version = 1

        observer_key = 'testkey1'
        mock_ctx = {'json_ld': {}}

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=True), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)), \
             patch('hepdata.modules.records.views.format_resource', return_value=mock_ctx) as mock_fmt_res, \
             patch('hepdata.modules.records.views.generate_license_data_by_id', return_value={}), \
             patch('hepdata.modules.records.views.render_template', return_value='rendered'):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            # Accept: text/html prevents auto-redirect to view_mode for text/plain file
            response = client.get(
                f'/record/resource/{resource.id}?landing_page=true&observer_key={observer_key}',
                headers={'Accept': 'text/html'}
            )
            assert response.status_code == 200

            # observer_key should be appended to content_url when key is verified
            call_args = mock_fmt_res.call_args[0]
            content_url = call_args[2]  # 3rd positional argument
            assert f'observer_key={observer_key}' in content_url

            # ctx['observer_key'] should be set with the verified key
            assert mock_ctx.get('observer_key') == observer_key
    finally:
        db.session.delete(resource)
        db.session.commit()


def test_get_resource_landing_page_format_resource_error(app, client):
    """
    Test that get_resource returns 404 when format_resource raises ValueError
    in landing_page mode.
    Covers lines 859-861: except ValueError: log.error; return abort(404).
    """
    from invenio_db import db
    from hepdata.modules.submission.models import DataResource

    resource = DataResource(
        file_location='http://example.com/error_resource.txt',
        file_type='url',
        file_description='Test error resource'
    )
    db.session.add(resource)
    db.session.commit()

    try:
        mock_hep_sub = Mock()
        mock_hep_sub.publication_recid = 55556
        mock_hep_sub.version = 1

        with patch('hepdata.modules.records.views.HEPSubmission.query') as mock_hep_query, \
             patch('hepdata.modules.records.views.verify_observer_key', return_value=False), \
             patch('hepdata.modules.records.views.get_version_count', return_value=(1, 1)), \
             patch('hepdata.modules.records.views.format_resource',
                   side_effect=ValueError('Test format error')):

            mock_hep_query.filter.return_value.first.return_value = mock_hep_sub

            # Accept: text/html prevents auto-redirect to view_mode
            response = client.get(
                f'/record/resource/{resource.id}?landing_page=true',
                headers={'Accept': 'text/html'}
            )
            # ValueError from format_resource should result in 404 response
            assert response.status_code == 404
    finally:
        db.session.delete(resource)
        db.session.commit()
