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

from invenio_assets import NpmBundle

dashboard_js = NpmBundle(
    'js/dashboard.js',
    'js/lib/typeahead.bundle.min.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.dashboard.%(version)s.js"
)
submission_vis_js = NpmBundle(
    'node_modules/crossfilter/crossfilter.min.js',
    'node_modules/dc/dc.min.js',
    'js/submissions_vis.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.submissions-vis.%(version)s.js",
    npm={
        "dc": "1.7.5",
        "crossfilter": "1.3.12"
    }
)

submission_css = NpmBundle(
    'node_modules/dc/dc.min.css',
    filters='cleancss',
    output='gen/hepdata.submission.%(version)s.css',
    npm={
        "dc": "1.7.5"
    }
)
