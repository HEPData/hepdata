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

"""JS/CSS bundles for theme."""

from flask_webpackext import WebpackBundle

theme = WebpackBundle(
    __name__,
    'assets',
    entry={
        'hepdata-styles': './scss/styles.scss',
        'hepdata-dashboard': './scss/dashboard.scss',
        'hepdata-record': './scss/record.scss',
        'hepdata-search': './scss/search.scss',
        'hepdata-submission': './scss/submission.scss',
        'hepdata-info': './scss/info-pages.scss',
        'toastr': './node_modules/toastr/toastr.scss',
        'bootstrap-filestyle-js': './js/lib/bootstrap-filestyle.min.js',
        'hepdata-page-js': './js/hepdata_page.js',
        'hepdata-home-js': './js/hepdata_home.js',
        'inspire-js': './js/inspire.js'
    },
    dependencies={
        "bootstrap-sass": "~3.3.5",
        "bootstrap": "~3.3.5",
        "font-awesome": "~4.6.3",
        "toastr": "~2.1.2"
    }
)
