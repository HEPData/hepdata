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

from flask_webpackext import WebpackBundle

record_js = WebpackBundle(
    __name__,
    'assets',
    entry={
        'hepdata-record-js': './js/hepdata_record_js.js',
        'hepdata-common-js': './js/hepdata_common.js',
        'hepdata-loaders-js': './js/hepdata_loaders.js',
        # 'js/hepdata_reviews.js',
        # 'js/hepdata_tables.js',
        # 'js/hepdata_vis_common.js',
        # 'js/hepdata_vis_heatmap.js',
        # 'js/hepdata_vis_histogram.js',
        # 'js/hepdata_vis_pie.js',
        # 'js/hepdata_vis_status.js',
    },
    dependencies={
        "clipboard": "~1.5.5",
        "d3": "~3.5.12",
        "d3-tip": "~0.6.7",
        "mathjax": "~2.7.0",
    }
)
