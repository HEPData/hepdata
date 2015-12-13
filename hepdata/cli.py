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

"""HEPData CLI module."""

from __future__ import absolute_import, print_function
from flask.ext.cli import with_appcontext
from invenio_base.app import create_cli
from .factory import create_app
from hepdata.ext.elasticsearch.api import reindex_all

cli = create_cli(create_app=create_app)

@cli.command()
@with_appcontext
def populate():
    """Populate the DB with sample records."""
    from hepdata.ext.elasticsearch.api import recreate_index
    from hepdata.modules.records.migrator.api import load_files
    recreate_index()

    files_to_load = ['ins1345354', 'ins1361912', 'ins1296861', 'ins1386475',
                     'ins116150', 'ins333513', 'ins1334140', 'ins1203852',
                     'ins1343107', 'ins1373912', 'ins1377585', 'ins1359451']
    load_files.delay(files_to_load)



@cli.command()
@with_appcontext
def reindex(start=-1, end=-1, batch=25, recreate=True):
    reindex_all(recreate=recreate, start=start, end=end, batch=batch)

