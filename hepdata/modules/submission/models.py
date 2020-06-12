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

"""Models for the HEPData Submission Workflow."""

from invenio_accounts.models import User
from sqlalchemy import TypeDecorator, types
from invenio_db import db
from datetime import datetime

submission_participant_link = db.Table(
    'submission_participant_link',
    db.Column('rec_id', db.Integer,
              db.ForeignKey('hepsubmission.id')),

    db.Column('participant_id', db.Integer,
              db.ForeignKey('submissionparticipant.id')))

data_reference_link = db.Table(
    'data_resource_link',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('hepsubmission.id')),

    db.Column('dataresource_id', db.Integer,
              db.ForeignKey('dataresource.id', ondelete='CASCADE'))
)


class LargeBinaryString(TypeDecorator):
    impl = types.LargeBinary

    def process_literal_param(self, value, dialect):
        if isinstance(value, str):
            value = value.encode('utf-8', errors='replace')

        return value

    process_bind_param = process_literal_param

    def process_result_value(self, value, dialect):
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='replace')

        return value


class HEPSubmission(db.Model):
    """
    This is the main submission object. It maintains the
    submissions to HEPData and who the coordinator and who the
    reviewers/uploaders are (via participants).
    """
    __tablename__ = "hepsubmission"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    publication_recid = db.Column(db.Integer)
    inspire_id = db.Column(db.String(128))

    data_abstract = db.Column(LargeBinaryString)

    resources = db.relationship("DataResource",
                                 secondary="data_resource_link",
                                 cascade="all,delete")

    # coordinators are already logged in to submit records,
    # so we know their User id.
    coordinator = db.Column(db.Integer, db.ForeignKey(User.id))
    participants = db.relationship("SubmissionParticipant",
                                   secondary="submission_participant_link",
                                   cascade="all,delete")

    # when this flag is set to 'ready', all data records will have an
    # invenio record created for them.
    overall_status = db.Column(db.String(128), default='todo')

    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    last_updated = db.Column(db.DateTime, nullable=True, default=datetime.utcnow, index=True)

    # this links to the latest version of the data files to be shown
    # in the submission and allows one to go back in time via the
    # interface to view various stages of the submission.
    version = db.Column(db.Integer, default=1)

    # the doi for the whole submission.
    doi = db.Column(db.String(128), nullable=True)

    reviewers_notified = db.Column(db.Boolean, default=False)


datafile_identifier = db.Table(
    'datafile_identifier',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('datasubmission.id')),
    db.Column('dataresource_id', db.Integer, db.ForeignKey('dataresource.id', ondelete='CASCADE'))
)

keyword_identifier = db.Table(
    'keyword_submission',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('datasubmission.id')),

    db.Column('keyword_id', db.Integer, db.ForeignKey('keyword.id', ondelete='CASCADE')))


class DataSubmission(db.Model):
    __tablename__ = "datasubmission"

    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)

    publication_recid = db.Column(db.Integer)
    publication_inspire_id = db.Column(db.String(128))

    location_in_publication = db.Column(db.String(256))
    name = db.Column(db.String(64))
    description = db.Column(LargeBinaryString)
    keywords = db.relationship("Keyword", secondary="keyword_submission",
                               cascade="all,delete")

    # the main data file, with the data table
    data_file = db.Column(db.Integer, db.ForeignKey("dataresource.id"))

    # supplementary files, such as code, links out to other resources etc.
    resources = db.relationship("DataResource", secondary="datafile_identifier",
                                       cascade="all,delete")

    doi = db.Column(db.String(128), nullable=True)

    # the record ID for the resulting record created on finalisation.
    associated_recid = db.Column(db.Integer)

    # when a new version is loaded, the version is increased and
    # maintained so people can go back in time
    # through a submissions review stages.
    version = db.Column(db.Integer, default=0)


class Keyword(db.Model):
    __tablename__ = "keyword"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name = db.Column(db.String(128))
    value = db.Column(db.String(128))


class License(db.Model):
    __tablename__ = "hepdata_license"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name = db.Column(db.String(256))
    url = db.Column(db.String(256))
    description = db.Column(LargeBinaryString)


class DataResource(db.Model):
    __tablename__ = "dataresource"

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True)

    file_location = db.Column(db.String(256))
    file_type = db.Column(db.String(64), default="json")
    file_description = db.Column(LargeBinaryString)

    file_license = db.Column(db.Integer, db.ForeignKey("hepdata_license.id"),
                             nullable=True)

    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                        index=True)


datareview_messages = db.Table('review_messages',
                               db.Column('datareview_id', db.Integer,
                                         db.ForeignKey('datareview.id')),
                               db.Column('message_id', db.Integer,
                                         db.ForeignKey(
                                             'message.id')))


class DataReview(db.Model):
    """
    Represent a data review including links to the messages
    made about a data record upload and its current status.
    """
    __tablename__ = "datareview"

    id = db.Column(
        db.Integer, primary_key=True,
        nullable=False, autoincrement=True)

    publication_recid = db.Column(db.Integer)
    data_recid = db.Column(db.Integer, db.ForeignKey("datasubmission.id"))

    creation_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    modification_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True,
        onupdate=datetime.utcnow)

    # as in, passed, attention, to do
    status = db.Column(db.String(20), default="todo")

    messages = db.relationship("Message",
                               secondary="review_messages",
                               cascade="all,delete")

    version = db.Column(db.Integer, default=0)


class Message(db.Model):
    """General message structure."""
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)

    user = db.Column(db.Integer, db.ForeignKey(User.id))
    message = db.Column(LargeBinaryString)

    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                              index=False)


class Question(db.Model):
    """Questions for a record are stored."""

    __tablename__ = "question"

    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)

    user = db.Column(db.Integer, db.ForeignKey(User.id))
    publication_recid = db.Column(db.Integer)

    question = db.Column(LargeBinaryString)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                              index=False)


class RecordVersionCommitMessage(db.Model):
    """Stores messages that can be attached to each submission once."""
    id = db.Column(
        db.Integer, primary_key=True,
        nullable=False, autoincrement=True)

    recid = db.Column(db.Integer)

    creation_date = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    version = db.Column(db.Integer, default=1)
    message = db.Column(LargeBinaryString)
