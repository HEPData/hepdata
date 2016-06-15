# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

from __future__ import absolute_import, print_function

from flask import Blueprint, render_template, current_app

from hepdata.version import __version__

blueprint = Blueprint(
    'hepdata_theme',
    __name__,
    url_prefix='',
    template_folder='templates',
    static_folder='static',
)


@blueprint.route('/')
def index():
    return render_template('hepdata_theme/home.html', ctx={"version": __version__})


@blueprint.route('/submission')
def submission_help():
    return render_template('hepdata_theme/pages/help.html')


@blueprint.route('/cookies')
def cookie_policy():
    return render_template('hepdata_theme/pages/cookies.html')


@blueprint.route('/about')
def about():
    return render_template('hepdata_theme/pages/about.html')


@blueprint.route('/terms')
def terms():
    return render_template('hepdata_theme/pages/terms.html')


def page_not_found(e):
    """Error handler to show a 404.html page in case of a 404 error."""
    return render_template(current_app.config['THEME_404_TEMPLATE']), 404


def internal_error(e):
    """Error handler to show a 500.html page in case of a 500 error."""
    return render_template(current_app.config['THEME_500_TEMPLATE']), 500


@blueprint.route('/ping')
def ping():
    return 'OK'
