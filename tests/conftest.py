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

"""HEPData Test Fixtures"""

from __future__ import absolute_import, print_function

import os

from invenio_accounts.models import Role, User
from invenio_db import db
import pytest

from hepdata.ext.elasticsearch.api import reindex_all
from hepdata.factory import create_app
from hepdata.modules.records.migrator.api import Migrator

@pytest.fixture()
def app(request):
    """Flask app fixture."""
    app = create_app()
    app.config.update(dict(
        TESTING=True,
        TEST_RUNNER="celery.contrib.test_runner.CeleryTestSuiteRunner",
        CELERY_ALWAYS_EAGER=True,
        CELERY_RESULT_BACKEND="cache",
        CELERY_CACHE_BACKEND="memory",
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql+psycopg2://localhost/hepdata')
    ))

    with app.app_context():
        db.drop_all()
        db.create_all()
        reindex_all(recreate=True)

        ctx = app.test_request_context()
        ctx.push()

        user_count = User.query.filter_by(email='test@hepdata.net').count()
        if user_count == 0:
            user = User(email='test@hepdata.net', password='hello1', active=True)
            admin_role = Role(name='admin')
            coordinator_role = Role(name='coordinator')

            user.roles.append(admin_role)
            user.roles.append(coordinator_role)

            db.session.add(admin_role)
            db.session.add(coordinator_role)
            db.session.add(user)
            db.session.commit()

    def teardown():
        with app.app_context():
            db.drop_all()
            ctx.pop()

    request.addfinalizer(teardown)

    return app


@pytest.fixture()
def migrator():
    return Migrator()


@pytest.fixture()
def identifiers():
    return [{"inspire_id": "ins1283842",
             "title": "Measurement of the forward-backward asymmetry "
                      "in the distribution of leptons in $t\\bar{t}$ "
                      "events in the lepton$+$jets channel",
             "data_tables": 14}
            ]
