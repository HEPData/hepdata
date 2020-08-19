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

"""Models for the HEPData Permissions."""
import uuid

from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy_utils import UUIDType
from hepdata.modules.submission.models import LargeBinaryString


class CoordinatorRequest(db.Model):
    """Stores coordinators, any text sent originally, and their collaboration."""
    id = db.Column(
        db.Integer, primary_key=True,
        nullable=False, autoincrement=True)

    user = db.Column(db.Integer, db.ForeignKey(User.id))
    collaboration = db.Column(db.String(512))
    message = db.Column(LargeBinaryString)

    approved = db.Column(db.Boolean, default=False)
    in_queue = db.Column(db.Boolean, default=True)


class SubmissionParticipant(db.Model):

    """
    This table stores information about the reviewers and
    uploaders of a HEPData submission.
    """
    __tablename__ = "submissionparticipant"

    id = db.Column(db.Integer, primary_key=True,
                   nullable=False, autoincrement=True)

    publication_recid = db.Column(db.Integer)

    full_name = db.Column(db.String(128))
    email = db.Column(db.String(128))
    affiliation = db.Column(db.String(128))
    invitation_cookie = db.Column(UUIDType, default=uuid.uuid4)

    # when the user logs in with their cookie,
    # this user_account should be updated.
    user_account = db.Column(db.Integer, db.ForeignKey(User.id))

    # e.g., reviewer or uploader
    role = db.Column(db.String(32), default='')
    # e.g. primary or reserve reviewer/uploader
    status = db.Column(db.String(32), default='reserve')
    action_date = db.Column(db.DateTime, nullable=True, index=True)
