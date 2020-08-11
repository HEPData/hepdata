#
# This file is part of HEPData.
# Copyright (C) 2020 CERN.
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

from invenio_db import db

from hepdata.modules.submission.models import DataSubmission, DataReview


def test_data_review_cascade(app):
    recid = "12345"
    datasubmission = DataSubmission(publication_recid=recid)
    db.session.add(datasubmission)
    db.session.commit()

    datareview = DataReview(publication_recid=recid,
                            data_recid=datasubmission.id)
    db.session.add(datareview)
    db.session.commit()

    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 1)
    assert(reviews[0] == datareview)

    # Delete datasubmission and see if datareview is deleted
    db.session.delete(datasubmission)
    db.session.commit()

    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 0)
