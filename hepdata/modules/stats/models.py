#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#

"""HEPData Stats Models."""

from invenio_db import db

class DailyAccessStatistic(db.Model):
    __tablename__ = "daily_access_statistic"

    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)

    publication_recid = db.Column(db.Integer)
    day = db.Column(db.Date, nullable=False)

    count = db.Column(db.Integer)
