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

"""JS/CSS bundles for theme."""

from __future__ import absolute_import, print_function

from flask_assets import Bundle
from invenio_assets import NpmBundle

css = NpmBundle(
    'scss/styles.scss',
    filters='scss, cleancss',
    depends=('scss/*.scss', ),
    output='gen/hepdata.%(version)s.css',
    npm={
        "bootstrap-sass": "~3.3.5",
        "font-awesome": "~4.4.0"
    }
)

record_css = NpmBundle(
    'scss/record.scss',
    filters='scss, cleancss',
    depends=('scss/*.scss', ),
    output='gen/hepdata_record.%(version)s.css',
    npm={
        "bootstrap-sass": "~3.3.5",
        "font-awesome": "~4.4.0"
    }
)

search_css = NpmBundle(
    'scss/search.scss',
    filters='scss, cleancss',
    depends=('scss/*.scss', ),
    output='gen/hepdata_search.%(version)s.css',
    npm={
        "bootstrap-sass": "~3.3.5",
        "font-awesome": "~4.4.0"
    }
)


js = NpmBundle(
    Bundle(
        'js/modernizr-custom.js',
        'js/dataviewer.js',
        filters='uglifyjs',
    ),

    filters='jsmin',
    output="gen/hepdata.%(version)s.js"
)

submission_js = NpmBundle(
    Bundle(
        'js/inspire.js',
        filters='uglifyjs',
    ),

    filters='jsmin',
    output="gen/hepdata-inspire.%(version)s.js"
)