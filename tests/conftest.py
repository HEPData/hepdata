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


from __future__ import absolute_import, print_function
import os

from invenio_db import InvenioDB, db
import pytest
from hepdata.factory import create_app
from hepdata.modules.records.migrator.api import Migrator


@pytest.fixture()
def app(request):
    """Flask app fixture."""
    app = create_app()
    app.config.update(dict(
        TESTING=True,
        CELERY_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'sqlite:///test.db')
    ))

    with app.app_context():
        db.create_all()

    def teardown():
        with app.app_context():
            db.drop_all()

    request.addfinalizer(teardown)

    return app


@pytest.fixture()
def migrator():
    return Migrator()


@pytest.fixture()
def identifiers():
    return [{"inspire_id": "ins1245023",
             "title": "High-statistics study of $K^0_S$ pair "
                      "production in two-photon collisions"},
            {"inspire_id": "ins731865",
             "title": "Observation of the Exclusive Reaction "
                      "$e^{+} e^{-} \to \phi \eta$ at "
                      "$\sqrt{s}$ = 10.58-GeV"}
            # {"inspire_id": "ins1183818",
            #  "title": "Measurements of the pseudorapidity "
            #           "dependence of the total transverse energy "
            #           "in proton-proton collisions at "
            #           "$\sqrt{s}=7$ TeV with ATLAS"},
            #
            # {"inspire_id": "ins1268975",
            #  "title": "Measurement of dijet cross sections in "
            #           "$pp$ collisions at 7 TeV centre-of-mass "
            #           "energy using the ATLAS detector"},
            #
            # {"inspire_id": "ins1306294",
            #  "title": "Measurements of the pseudorapidity "
            #           "dependence of the total transverse "
            #           "energy in proton-proton collisions at "
            #           "$\sqrt{s}=7$ TeV with ATLAS"},
            #
            # {"inspire_id": "ins1362183",
            #  "title": "Measurement of the Z production cross "
            #           "section in pp collisions at 8 TeV and "
            #           "search for anomalous triple gauge boson "
            #           "couplings"}
            ]
