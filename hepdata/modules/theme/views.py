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

"""Theme blueprint in order for template and static files to be loaded."""

import re

from flask import Blueprint, render_template, current_app, redirect, request, url_for
from hepdata_validator import LATEST_SCHEMA_VERSION, RAW_SCHEMAS_URL

from hepdata.modules.email.utils import send_flask_message_email
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.utils.miscellaneous import sanitize_html
from hepdata.version import __version__

blueprint = Blueprint(
    'hepdata_theme',
    __name__,
    url_prefix='',
    template_folder='templates',
    static_folder='static',
)


@blueprint.record_once
def init(state):
    """Init app."""
    app = state.app
    # Customise flask-security emails
    security = app.extensions['security']

    @security.send_mail_task
    def send_hepdata_mail(msg):
        send_flask_message_email(msg)

    @security.mail_context_processor
    def security_mail_processor():
        site_url = app.config.get('SITE_URL', 'https://www.hepdata.net')
        return dict(site_url=site_url)

    @app.context_processor
    def set_banner_msg():
        banner_msg = app.config.get('BANNER_MSG', None)
        banner_msg = sanitize_html(banner_msg)
        return dict(banner_msg=banner_msg)


@blueprint.route('/')
def index():
    return render_template('hepdata_theme/home.html', ctx={"sw_version": __version__})


@blueprint.route('/submission')
def submission_help():
    return render_template('hepdata_theme/pages/help.html')


@blueprint.route('/submission/schemas/<path:jsonschema>')
def submission_schema(jsonschema):
    if not re.match(r"[\d+\.]+/.*", jsonschema):
        jsonschema = LATEST_SCHEMA_VERSION + '/' + jsonschema

    return redirect(RAW_SCHEMAS_URL + '/' + jsonschema)


@blueprint.route('/cookies')
def cookie_policy():
    return render_template('hepdata_theme/pages/cookies.html')


@blueprint.route('/about')
def about():
    return render_template('hepdata_theme/pages/about.html')


@blueprint.route('/terms')
def terms():
    return render_template('hepdata_theme/pages/terms.html')


@blueprint.route('/formats')
def formats():
    ctx = {}
    sample_resource = None
    hepsubmission = get_latest_hepsubmission(inspire_id='1748602')

    if hepsubmission:
        workspace_resources = [r for r in hepsubmission.resources if r.file_location.endswith('HEPData_workspaces.tar.gz')]
        if workspace_resources:
            sample_resource = workspace_resources[0]
            if sample_resource:
                sample_resource_url = url_for(
                    'hepdata_records.get_resource',
                    resource_id=sample_resource.id, landing_page=True,
                    _external=True)
                sample_resource_doi = sample_resource.doi or '10.17182/hepdata.89408.v1/r2'

    if not sample_resource:
        sample_resource_url = 'https://www.hepdata.net/record/resource/997020?landing_page=true'
        sample_resource_doi = '10.17182/hepdata.89408.v1/r2'

    ctx = {
        'sample_resource_url': sample_resource_url,
        'sample_resource_doi': sample_resource_doi
    }
    return render_template('hepdata_theme/pages/formats.html', ctx=ctx)


@blueprint.route('/record/invalid_doi')
def invalid_doi():
    return render_template(current_app.config['INVALID_DOI_TEMPLATE']), 410


def page_forbidden(e):
    """Error handler to show a 403.html page in case of a 403 error."""
    return render_template(current_app.config['THEME_403_TEMPLATE'],
                           ctx={"name": type(e).__name__, "error": str(e)}), 403


def page_not_found(e):
    """Error handler to show a 404.html page in case of a 404 error."""
    return render_template(current_app.config['THEME_404_TEMPLATE'],
                           ctx={"name": type(e).__name__, "error": str(e)}), 404


def internal_error(e):
    """Error handler to show a 500.html page in case of a 500 error."""
    return render_template(current_app.config['THEME_500_TEMPLATE'],
                           ctx={"name": type(e).__name__, "error": str(e)}), 500


def redirect_nonwww():
    if current_app.config.get('PRODUCTION_MODE', False) and 'www' not in request.url:
        return redirect(request.url.replace('://', '://www.'), code=301)


@blueprint.route('/ping')
def ping():
    return 'OK'
