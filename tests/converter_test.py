# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.
import os.path
import responses
import zipfile
from unittest.mock import Mock, patch

from hepdata.config import CFG_CONVERTER_URL
from hepdata.modules.converter.tasks import convert_and_store
from hepdata.modules.records.utils.old_hepdata import mock_import_old_record


def test_convert_and_store_invalid(app, capsys):
    with app.app_context():
        convert_and_store('12345678', 'test_format', True)
        captured = capsys.readouterr()
        assert(captured.out == "Unable to find a matching submission for 12345678\n")


@responses.activate
def test_convert_and_store_valid_yaml(app, capsys, load_submission):
    with app.app_context():
        # Open a .tar.gz file to mock the call to the converter
        base_dir = os.path.dirname(os.path.realpath(__file__))
        test_tar_gz_file = os.path.join(base_dir, 'test_data', '1396331.tar.gz')
        with open(test_tar_gz_file, "rb") as stream:
            responses.add(responses.GET, app.config.get('CFG_CONVERTER_URL', CFG_CONVERTER_URL) + '/convert',
                          status=200, headers={'mimetype': 'application/x-gzip'},
                          body=stream.read(), stream=True)

        capsys.readouterr()
        convert_and_store('1487726', 'yaml', True)
        captured_lines = capsys.readouterr().out.splitlines()

        assert(captured_lines[0] == "Creating yaml conversion for ins1487726")
        print(captured_lines)
        assert(captured_lines[1].startswith("File for ins1487726 created successfully"))
        file_path = captured_lines[1].split()[-1]
        assert(file_path.endswith("HEPData-ins1487726-v1-yaml.tar.gz"))
        assert(os.path.isfile(file_path))


def test_convert_and_store_valid_original(app, capsys, load_submission):
    with app.app_context():
        capsys.readouterr()
        convert_and_store('1487726', 'original', True)
        captured_lines = capsys.readouterr().out.splitlines()
        assert(captured_lines[0] == "Creating original conversion for ins1487726")
        assert(captured_lines[1].startswith("File created at "))
        file_path = captured_lines[1].split()[-1]
        assert(file_path.endswith("HEPData-ins1487726-v1.zip"))
        assert(os.path.isfile(file_path))


def test_convert_and_store_valid_original_with_old_resources(app, capsys):
    with app.app_context():
        # Create submission with resources
        mock_import_old_record()

        capsys.readouterr()
        convert_and_store('1299143', 'original', True)
        captured_lines = capsys.readouterr().out.splitlines()
        assert(captured_lines[0] == 'Creating original conversion for ins1299143')
        assert(captured_lines[1].startswith("Creating archive at "))
        file_path = captured_lines[1].split()[-1]
        assert('/converted/' in file_path)
        assert(file_path.endswith("HEPData-ins1299143-v1.zip"))
        assert(captured_lines[2] == 'File created at %s' % file_path)

        assert(os.path.isfile(file_path))
        # Check contents of zip
        with zipfile.ZipFile(file_path) as zip:
            contents = zip.namelist()
            assert(len(contents) == 99)
            # Check for a sample of filenames from yaml and resources
            for f in ['submission.yaml', 'Table_1.yaml', 'figFigure7a.png']:
                assert(f in contents)

            # Check submission file has been updated with new resource location
            with zip.open('submission.yaml') as f:
                for line in f.readlines():
                    line_str = line.decode()
                    if 'location' in line_str:
                        assert('/resource/' not in line_str)


def test_download_submission_with_recid_version_access_control(app, client):
    """
    Test that download_submission_with_recid returns 403 when a user without
    permissions tries to access an unpublished version.
    """
    recid = 12345
    version = 2  # Trying to access the latest unpublished version

    with patch('hepdata.modules.converter.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.converter.views.get_version_count') as mock_version_count:

        mock_verify.return_value = False
        # User can see 1 version (finished), but there are 2 total
        mock_version_count.return_value = (1, 2)

        response = client.get(f'/download/submission/{recid}/{version}/yaml')
        assert response.status_code == 403


def test_download_submission_with_inspire_id_version_access_control(app, client):
    """
    Test that download_submission_with_inspire_id returns 403 when a user
    without permissions tries to access an unpublished version.
    """
    inspire_id = 'ins1487726'
    version = 2  # Trying to access the latest unpublished version

    with patch('hepdata.modules.converter.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.converter.views.get_version_count') as mock_version_count, \
         patch('hepdata.modules.converter.views.get_latest_hepsubmission') as mock_sub:

        mock_sub.return_value = Mock(publication_recid=99999)
        mock_verify.return_value = False
        # User can see 1 version (finished), but there are 2 total
        mock_version_count.return_value = (1, 2)

        response = client.get(f'/download/submission/{inspire_id}/{version}/yaml')
        assert response.status_code == 403


def test_download_submission_with_inspire_id_older_version(app, client):
    """
    Test that download_submission_with_inspire_id retrieves the correct
    older version (elif version < version_count_all branch).
    """
    inspire_id = '1487726'

    mock_submission = Mock()
    mock_submission.publication_recid = 99998
    mock_submission.inspire_id = inspire_id
    mock_submission.version = 1
    mock_submission.overall_status = 'finished'

    with patch('hepdata.modules.converter.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.converter.views.get_version_count') as mock_version_count, \
         patch('hepdata.modules.converter.views.get_latest_hepsubmission') as mock_sub, \
         patch('hepdata.modules.converter.views.HEPSubmission') as mock_hepsub_class, \
         patch('hepdata.modules.converter.views.download_submission') as mock_download:

        mock_sub.return_value = mock_submission
        mock_verify.return_value = False
        # User can see 1 version (finished), but there are 2 total
        mock_version_count.return_value = (1, 2)
        mock_hepsub_class.query.filter_by.return_value.first.return_value = mock_submission
        mock_download.return_value = 'downloaded'

        response = client.get(f'/download/submission/ins{inspire_id}/1/yaml')
        # Should have called download_submission with version 1
        mock_download.assert_called_once()


def test_download_data_table_observer_key_not_verified(app, client):
    """
    Test that download_data_table_by_recid sets observer_key to None
    when the key is not verified (covers the if not key_verified path).
    """
    recid = 11111

    mock_datasubmission = Mock()
    mock_datasubmission.publication_recid = recid
    mock_datasubmission.id = 1
    mock_datasubmission.version = 1
    mock_datasubmission.name = 'Table 1'

    with patch('hepdata.modules.converter.views.verify_observer_key') as mock_verify, \
         patch('hepdata.modules.converter.views.get_version_count') as mock_version_count, \
         patch('hepdata.modules.converter.views.DataSubmission') as mock_datasub, \
         patch('hepdata.modules.converter.views.download_datatable') as mock_download:

        mock_verify.return_value = False  # Key NOT verified
        mock_version_count.return_value = (1, 1)  # Same count, no permission issue
        mock_datasub.query.filter_by.return_value.one.return_value = mock_datasubmission
        mock_download.return_value = 'downloaded'

        response = client.get(
            f'/download/table/{recid}/Table 1/yaml?observer_key=invalidkey'
        )
        # When key is not verified, download_datatable should be called with observer_key=None
        mock_download.assert_called_once()
        call_kwargs = mock_download.call_args[1]
        assert call_kwargs.get('observer_key') is None


def test_download_datatable_json_with_observer_key(app, client):
    """
    Test that download_datatable includes observer_key in the redirect URL
    when file_format is 'json' and observer_key is provided.
    """
    from hepdata.modules.converter.views import download_datatable

    mock_datasubmission = Mock()
    mock_datasubmission.publication_recid = 22222
    mock_datasubmission.id = 5
    mock_datasubmission.version = 1

    with app.test_request_context('/'):
        response = download_datatable(
            mock_datasubmission,
            'json',
            observer_key='testkey1'
        )
        # Should redirect with observer_key in URL
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        assert 'observer_key=testkey1' in location


def test_download_datatable_json_without_observer_key(app, client):
    """
    Test that download_datatable redirects without observer_key when
    observer_key is None (covers the if observer_key: branch).
    """
    from hepdata.modules.converter.views import download_datatable

    mock_datasubmission = Mock()
    mock_datasubmission.publication_recid = 33333
    mock_datasubmission.id = 6
    mock_datasubmission.version = 1

    with app.test_request_context('/'):
        response = download_datatable(
            mock_datasubmission,
            'json',
            observer_key=None
        )
        # Should redirect without observer_key
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        assert 'observer_key' not in location
