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

"""Jinja utilities for Invenio."""

from __future__ import absolute_import, print_function

from operator import or_
from invenio_accounts.models import User
from hepdata.modules.records.models import SubmissionParticipant

__author__ = 'eamonnmaguire'

from flask.ext.login import current_user
from invenio_db import db

from . import config

from .views import blueprint


class HEPDataRecords(object):
    """HEPData records extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)
            self.setup_app(app)

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.register_blueprint(blueprint)
        app.extensions['hepdata-records'] = self

    def init_config(self, app):
        """Initialize configuration."""
        for k in dir(config):
            if k.startswith('HEPDATA_'):
                app.config.setdefault(k, getattr(config, k))

    def setup_app(self, app):

        def user_is_admin_or_coordinator():
            if current_user and current_user.is_authenticated:
                id = int(current_user.get_id())
                with db.session.no_autoflush:
                    roles = User.query.filter(User.id == id).filter(
                        or_(User.roles.any(name='coordinator'),
                            User.roles.any(name='admin'))).all()

                return len(roles) > 0
            return False

        @app.context_processor
        def is_coordinator_or_admin():
            """
                Determines if the user is an admin or coordinator given their
                assigned accRoles.
                :return: true if the user is a coordinator or administrator,
                false otherwise
            """
            result = user_is_admin_or_coordinator()
            return dict(
                user_is_coordinator_or_admin=result)

        @app.context_processor
        def show_dashboard():
            """
            Determines if a user should be able to see the submission overview page.
            :return:
            """
            if current_user and current_user.is_authenticated:
                if user_is_admin_or_coordinator():
                    return dict(show_dashboard=True)
                else:
                    id = int(current_user.get_id())
                    with db.session.no_autoflush:
                        submissions = SubmissionParticipant.query.filter(
                            SubmissionParticipant.user_account == id).count()

                    return dict(show_dashboard=submissions > 0)

            return dict(show_dashboard=False)
