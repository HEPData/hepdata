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

"""Jinja utilities for Invenio."""

import pkg_resources

from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.theme.views import page_forbidden
from hepdata.modules.theme.views import internal_error
from hepdata.modules.theme.views import page_not_found
from hepdata.modules.theme.views import redirect_nonwww
from flask_login import current_user
from invenio_db import db

from hepdata.utils.users import user_is_admin_or_coordinator, user_is_admin
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

        app.register_error_handler(403, page_forbidden)
        app.register_error_handler(404, page_not_found)
        app.register_error_handler(500, internal_error)

        app.before_request(redirect_nonwww)

    def init_config(self, app):
        """Initialize configuration."""
        for k in dir(config):
            if k.startswith('HEPDATA_'):
                app.config.setdefault(k, getattr(config, k))

    def setup_app(self, app):

        try:
            from flask_cors import CORS
            pkg_resources.get_distribution('Flask-CORS')

            # CORS can be configured using CORS_* configuration variables.
            CORS(app)

        except pkg_resources.DistributionNotFound:
            raise RuntimeError(
                "You must use `pip install flask-cors` to "
                "enable CORS support.")

        @app.context_processor
        def is_coordinator_or_admin():
            """
                Determines if the user is an admin or coordinator given their
                assigned accRoles.

                :return: true if the user is a coordinator or administrator,
                false otherwise
            """
            result = user_is_admin_or_coordinator(current_user)
            return dict(
                user_is_coordinator_or_admin=result)

        @app.context_processor
        def is_admin():
            """
                Determines if the user is an admin given their
                assigned accRoles.

                :return: true if the user is an administrator,
                false otherwise
            """
            result = user_is_admin(current_user)
            return dict(user_is_admin=result)

        @app.context_processor
        def show_dashboard():
            """
            Determines if a user should be able to see the submission overview page.

            :return:
            """
            if current_user and current_user.is_authenticated:
                if user_is_admin_or_coordinator(current_user):
                    return dict(show_dashboard=True)
                else:
                    id = int(current_user.get_id())
                    with db.session.no_autoflush:
                        submissions = SubmissionParticipant.query.filter(
                            SubmissionParticipant.user_account == id).count()

                    return dict(show_dashboard=submissions > 0)

            return dict(show_dashboard=False)
