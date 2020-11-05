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

import logging
import os.path

from invenio_db import db

from hepdata.modules.submission.models import DataReview, DataResource, DataSubmission, \
    Message, receive_before_flush


def test_data_submission_cascades(app):
    # Create a data submission
    recid = "12345"
    datasubmission = DataSubmission(publication_recid=recid)
    db.session.add(datasubmission)
    db.session.commit()

    # Add a data review with a message
    message = Message(user=1, message="Test review message")
    datareview = DataReview(publication_recid=recid,
                            data_recid=datasubmission.id,
                            messages=[message])
    db.session.add(datareview)
    db.session.commit()

    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 1)
    assert(reviews[0] == datareview)
    messages = Message.query.all()
    assert(len(messages) == 1)

    # Add some data resources with files
    files_dir = os.path.join(app.config['CFG_DATADIR'], 'models_test')
    os.makedirs(files_dir, exist_ok=True)

    resources = []

    for i in range(3):
        file_path = os.path.join(files_dir, f'file{i}.txt')
        f = open(file_path, 'w')
        f.close()
        dataresource = DataResource(file_location=file_path, file_type="data")
        db.session.add(dataresource)
        db.session.commit()
        resources.append(dataresource)

    assert(len(os.listdir(files_dir)) == 3)

    datasubmission.data_file = resources[0].id
    datasubmission.resources = resources[1:]
    db.session.add(datasubmission)
    db.session.commit()

    # Check we can find resources in db
    dataresources = DataResource.query.filter(
                        DataResource.id.in_([x.id for x in resources])
                    ).all()
    assert(len(dataresources) == 3)

    # Delete datasubmission
    db.session.delete(datasubmission)
    db.session.commit()

    # Check that datareview is deleted
    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 0)
    # Check that message is deleted
    messages = Message.query.all()
    assert(len(messages) == 0)

    # Check all resources have been deleted
    dataresources = DataResource.query.filter(
                        DataResource.id.in_([x.id for x in resources])
                    ).all()

    assert(len(dataresources) == 0)

    # Check files are also deleted
    assert(os.listdir(files_dir) == [])

    # Tidy up
    os.rmdir(files_dir)


def test_data_review_cascades(app):
    # Create a data submission
    recid = "12345"
    datasubmission = DataSubmission(publication_recid=recid)
    db.session.add(datasubmission)
    db.session.commit()

    # Add a data review with a message
    message = Message(user=1, message="Test review message")
    datareview = DataReview(publication_recid=recid,
                            data_recid=datasubmission.id,
                            messages=[message])
    db.session.add(datareview)
    db.session.commit()

    # Check that message is created
    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 1)
    assert(len(reviews[0].messages) == 1)
    assert(reviews[0].messages[0].message == message.message)

    review_messages = list(db.engine.execute("select * from review_messages where datareview_id = %s" % datareview.id))
    assert(len(review_messages) == 1)
    assert(review_messages[0].datareview_id == datareview.id)

    db.session.delete(datareview)
    db.session.commit()

    # Check that datareview is deleted
    reviews = DataReview.query.filter_by(publication_recid=recid).all()
    assert(len(reviews) == 0)

    # Check that message is deleted
    messages = Message.query.filter_by(id=review_messages[0].message_id).all()
    assert(len(messages) == 0)


def test_receive_before_flush_errors(app, mocker, caplog):
    # Test that errors are logged in receive_before_flush
    # We mimic errors by providing unpersisted objects to the DataResource and
    # DataReview queries using mocking, so that they cannot successfully be
    # deleted from the db
    caplog.set_level(logging.ERROR)

    recid = "12345"
    datasubmission = DataSubmission(publication_recid=recid)
    db.session.add(datasubmission)
    db.session.commit()

    mockResourceFilterBy = mocker.Mock(first=lambda: DataResource())
    mockResourceQuery = mocker.Mock(filter_by=lambda id: mockResourceFilterBy)
    mockDataResource = mocker.Mock(query=mockResourceQuery)

    mocker.patch('hepdata.modules.submission.models.DataResource',
                 mockDataResource)

    mockReviewFilterBy = mocker.Mock(all=lambda: [DataReview()])
    mockReviewQuery = mocker.Mock(filter_by=lambda data_recid: mockReviewFilterBy)
    mockDataReview = mocker.Mock(query=mockReviewQuery)

    mocker.patch('hepdata.modules.submission.models.DataReview',
                 mockDataReview)

    db.session.delete(datasubmission)
    db.session.commit()

    # Last error logs are what we're looking for
    assert(len(caplog.records) == 2)

    assert(caplog.records[0].levelname == "ERROR")
    assert(caplog.records[0].msg.startswith(
        "Unable to delete data resource with id None whilst deleting data submission id 1. Error was: Instance '<DataResource at "
    ))
    assert(caplog.records[0].msg.endswith(
        " is not persisted"
    ))

    assert(caplog.records[1].levelname == "ERROR")
    assert(caplog.records[1].msg.startswith(
        "Unable to delete review with id None whilst deleting data submission id 1. Error was: Instance '<DataReview at "
    ))
    assert(caplog.records[1].msg.endswith(
        " is not persisted"
    ))
