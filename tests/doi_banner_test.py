# coding=utf-8

import os
from unittest.mock import patch

from hepdata.modules.doi_banner import views as doi_banner_views


def _mock_search_result(total, inspire_id='1245023'):
    hits = []
    if total > 0:
        hits = [{'_source': {'inspire_id': inspire_id}}]

    return {
        'hits': {
            'total': {'value': total},
            'hits': hits
        }
    }


def test_resolve_doi_data_redirects_to_record(client):
    doi = '10.1093/ptep/ptt097'

    with patch('hepdata.modules.doi_banner.views.get_records_matching_field') as mock_search:
        mock_search.return_value = _mock_search_result(total=1, inspire_id='1245023')

        response = client.get(f'/doidata/{doi}', follow_redirects=False)

        assert response.status_code == 302
        assert response.headers['Location'] == '/record/ins1245023'
        mock_search.assert_called_once_with('doi', doi, source={"includes": ['inspire_id']})


def test_resolve_doi_data_returns_404_when_not_found(client):
    doi = '10.1093/ptep/ptt404'

    with patch('hepdata.modules.doi_banner.views.get_records_matching_field') as mock_search:
        mock_search.return_value = _mock_search_result(total=0)

        response = client.get(f'/doidata/{doi}')

        assert response.status_code == 404
        mock_search.assert_called_once_with('doi', doi, source={"includes": ['inspire_id']})


def test_get_doi_banner_returns_hepdata_banner_if_record_exists(client):
    doi = '10.1093/ptep/ptt097'

    with patch('hepdata.modules.doi_banner.views.get_records_matching_field') as mock_search:
        mock_search.return_value = _mock_search_result(total=1)

        response = client.get(f'/doibanner/{doi}')

        expected_path = os.path.join(doi_banner_views.base_dir, 'static/img/hepdata-doi-banner.png')
        with open(expected_path, 'rb') as banner:
            expected_content = banner.read()

        assert response.status_code == 200
        assert response.mimetype == 'image/png'
        assert response.data == expected_content
        mock_search.assert_called_once_with('doi', doi, source={"includes": ['inspire_id']})


def test_get_doi_banner_returns_1px_if_record_does_not_exist(client):
    doi = '10.1093/ptep/ptt404'

    with patch('hepdata.modules.doi_banner.views.get_records_matching_field') as mock_search:
        mock_search.return_value = _mock_search_result(total=0)

        response = client.get(f'/doibanner/{doi}')

        expected_path = os.path.join(doi_banner_views.base_dir, 'static/img/1px.png')
        with open(expected_path, 'rb') as one_px:
            expected_content = one_px.read()

        assert response.status_code == 200
        assert response.mimetype == 'image/png'
        assert response.data == expected_content
        mock_search.assert_called_once_with('doi', doi, source={"includes": ['inspire_id']})

