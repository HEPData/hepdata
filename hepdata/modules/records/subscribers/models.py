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

"""HEPData Subscribers Model."""

from invenio_db import db

subscriber = db.Table(
    'subscriber',
    db.Column('publication_recid', db.Integer,
              db.ForeignKey('record_subscribers.publication_recid')),

    db.Column('user_id', db.Integer,
              db.ForeignKey('accounts_user.id')))


class Subscribers(db.Model):
    """
    WatchList is the main model for storing the query to be made for
    a watched query and the user who is watching it.
    """
    __tablename__ = "record_subscribers"
    publication_recid = db.Column(db.Integer, primary_key=True)

    subscribers = db.relationship("User",
                                  secondary="subscriber",
                                  cascade="all,delete")
