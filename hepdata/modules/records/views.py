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

"""Blueprint for HEPData-Records."""

from __future__ import absolute_import, print_function

import idutils
from flask import Blueprint, current_app


blueprint = Blueprint(
    'hepdata_records',
    __name__,
    template_folder='templates'
)

#
# Persistent identifiers template filters
#
@blueprint.app_template_test()
def local_doi(value):
    """Test if a DOI is a local DOI."""
    prefixes = current_app.config.get('ZENODO_LOCAL_DOI_PREFIXES', [])
    return prefixes and any([value.startswith(p) for p in prefixes])


@blueprint.app_template_filter('relation_title')
def relation_title(relation):
    """Map relation type to title."""
    return dict(current_app.config['ZENODO_RELATION_TYPES']).get(relation) or \
        relation


@blueprint.app_template_filter('pid_url')
def pid_url(identifier, scheme=None):
    """Convert persistent identifier into a link."""
    if scheme is None:
        try:
            scheme = idutils.detect_identifier_schemes(identifier)[0]
        except IndexError:
            scheme = None
    if scheme and identifier:
        return idutils.to_url(identifier, scheme)
    return ""
