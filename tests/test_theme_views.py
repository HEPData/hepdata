# -*- coding: utf-8 -*-
#
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

"""Tests for hepdata/modules/theme/views.py."""

from unittest.mock import patch

from hepdata.modules.theme.views import (
    invalid_doi,
    page_forbidden,
    page_not_found,
    internal_error,
    redirect_nonwww,
    ping,
)


class TestInvalidDoi:
    """Tests for the invalid_doi view."""

    def test_invalid_doi_returns_410(self, app):
        """GET /record/invalid_doi returns 410 status code."""
        with app.test_client() as client:
            response = client.get('/record/invalid_doi')
            assert response.status_code == 410

    def test_invalid_doi_renders_template(self, app):
        """invalid_doi renders the template from INVALID_DOI_TEMPLATE config."""
        with app.test_request_context('/record/invalid_doi'):
            with patch('hepdata.modules.theme.views.render_template') as mock_render:
                mock_render.return_value = 'rendered'
                result, status = invalid_doi()
                mock_render.assert_called_once_with(
                    app.config['INVALID_DOI_TEMPLATE']
                )
                assert status == 410


class TestPageForbidden:
    """Tests for the page_forbidden error handler."""

    def test_page_forbidden_returns_403(self, app):
        """page_forbidden returns 403 status code."""
        with app.test_request_context('/'):
            error = PermissionError("Access denied")
            _, status = page_forbidden(error)
            assert status == 403

    def test_page_forbidden_renders_template_with_context(self, app):
        """page_forbidden renders THEME_403_TEMPLATE with error info in ctx."""
        with app.test_request_context('/'):
            with patch('hepdata.modules.theme.views.render_template') as mock_render:
                mock_render.return_value = 'rendered'
                error = PermissionError("Not allowed")
                result, status = page_forbidden(error)
                mock_render.assert_called_once_with(
                    app.config['THEME_403_TEMPLATE'],
                    ctx={"name": "PermissionError", "error": "Not allowed"}
                )
                assert status == 403


class TestPageNotFound:
    """Tests for the page_not_found error handler."""

    def test_page_not_found_returns_404(self, app):
        """page_not_found returns 404 status code."""
        with app.test_request_context('/'):
            error = LookupError("Resource missing")
            _, status = page_not_found(error)
            assert status == 404

    def test_page_not_found_renders_template_with_context(self, app):
        """page_not_found renders THEME_404_TEMPLATE with error info in ctx."""
        with app.test_request_context('/'):
            with patch('hepdata.modules.theme.views.render_template') as mock_render:
                mock_render.return_value = 'rendered'
                error = LookupError("Not found")
                result, status = page_not_found(error)
                mock_render.assert_called_once_with(
                    app.config['THEME_404_TEMPLATE'],
                    ctx={"name": "LookupError", "error": "Not found"}
                )
                assert status == 404


class TestInternalError:
    """Tests for the internal_error error handler."""

    def test_internal_error_returns_500(self, app):
        """internal_error returns 500 status code."""
        with app.test_request_context('/'):
            error = RuntimeError("Something went wrong")
            _, status = internal_error(error)
            assert status == 500

    def test_internal_error_renders_template_with_context(self, app):
        """internal_error renders THEME_500_TEMPLATE with error info in ctx."""
        with app.test_request_context('/'):
            with patch('hepdata.modules.theme.views.render_template') as mock_render:
                mock_render.return_value = 'rendered'
                error = RuntimeError("Internal failure")
                result, status = internal_error(error)
                mock_render.assert_called_once_with(
                    app.config['THEME_500_TEMPLATE'],
                    ctx={"name": "RuntimeError", "error": "Internal failure"}
                )
                assert status == 500


class TestRedirectNonwww:
    """Tests for the redirect_nonwww before-request hook."""

    def test_redirect_nonwww_in_production_without_www(self, app):
        """redirect_nonwww redirects to www URL in production mode when 'www' is absent."""
        app.config['PRODUCTION_MODE'] = True
        with app.test_request_context('http://hepdata.net/about'):
            response = redirect_nonwww()
            assert response is not None
            assert response.status_code == 301
            assert 'www.hepdata.net' in response.location

    def test_redirect_nonwww_in_production_with_www(self, app):
        """redirect_nonwww does NOT redirect when 'www' is already in the URL."""
        app.config['PRODUCTION_MODE'] = True
        with app.test_request_context('http://www.hepdata.net/about'):
            response = redirect_nonwww()
            assert response is None

    def test_redirect_nonwww_not_in_production(self, app):
        """redirect_nonwww does NOT redirect when PRODUCTION_MODE is False."""
        app.config['PRODUCTION_MODE'] = False
        with app.test_request_context('http://hepdata.net/about'):
            response = redirect_nonwww()
            assert response is None


class TestPing:
    """Tests for the ping view."""

    def test_ping_returns_ok(self, app):
        """GET /ping returns 'OK' with 200 status."""
        with app.test_client() as client:
            response = client.get('/ping')
            assert response.status_code == 200
            assert response.data == b'OK'

    def test_ping_directly(self, app):
        """ping() function returns the string 'OK'."""
        with app.test_request_context('/ping'):
            assert ping() == 'OK'

