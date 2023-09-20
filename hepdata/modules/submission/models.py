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

import logging
import os

from invenio_accounts.models import User
from sqlalchemy import TypeDecorator, types, event
from invenio_db import db
from datetime import datetime

logging.basicConfig()
log = logging.getLogger(__name__)

data_reference_link = db.Table(
    'data_resource_link',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('hepsubmission.id')),

    db.Column('dataresource_id', db.Integer,
              db.ForeignKey('dataresource.id', ondelete='CASCADE'))
)


class LargeBinaryString(TypeDecorator):
    """
    Decorator for unicode strings which are stored in the DB as LargeBinary objects,
    to allow them to be treated as strings in python3
    """
    impl = types.LargeBinary

    def process_literal_param(self, value, dialect):
        """
        Encodes and returns string object.
        """
        if isinstance(value, str):
            value = value.encode('utf-8', errors='replace')

        return value

    process_bind_param = process_literal_param

    def process_result_value(self, value, dialect):
        """
        Encodes and returns string object.
        """
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

    # id is a unique id for each version of a submission
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # publication_recid remains the same for each version of a submission
    # and is used as the document id in opensearch and as the record id
    publication_recid = db.Column(db.Integer)
    inspire_id = db.Column(db.String(128))

    data_abstract = db.Column(LargeBinaryString)

    resources = db.relationship("DataResource",
                                 secondary="data_resource_link",
                                 cascade="all,delete")

    # coordinators are already logged in to submit records,
    # so we know their User id.
    coordinator = db.Column(db.Integer, db.ForeignKey(User.id))

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

    related_recids = db.relationship("RelatedRecid", secondary="relatedrecid_identifier",
                               cascade="all,delete")


    def get_related_to_this_hepsubmissions(self):
        """
        Queries the database for all records in the RelatedRecId table
        that have THIS record's id as a related record.
        Then returns the HEPSubmission object marked in the RelatedRecid table.
        Returns only submissions marked as 'finished'
        :return: [list] List containing related records.
        """
        related_submissions = (
            HEPSubmission.query
            .join(RelatedRecid, RelatedRecid.this_recid == HEPSubmission.publication_recid)
            .filter(RelatedRecid.related_recid == self.publication_recid)
            .filter(HEPSubmission.overall_status == 'finished') # Only finished submissions
            .all())
        return related_submissions

    def get_related_hepsubmissions(self):
        """
        Queries the database for all HEPSubmission objects contained in
        this object's related record ID list.
        (All submissions this one is relating to)
        :return: [list] A list of HEPSubmission objects
        """
        related_submissions = []
        for related in self.related_recids:
            data_submission = (
                HEPSubmission.query
                    .filter(HEPSubmission.publication_recid == related.related_recid)
                    .filter(HEPSubmission.overall_status == 'finished').first())
            if data_submission:
                related_submissions.append(data_submission)
        return related_submissions


# Declarations of the helper tables used to manage many-to-many relationships.
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
    db.Column('keyword_id', db.Integer, db.ForeignKey('keyword.id', ondelete='CASCADE'))
)

relatedtable_identifier = db.Table(
    'relatedtable_identifier',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('datasubmission.id')),
    db.Column('relatedtable_id', db.Integer, db.ForeignKey('relatedtable.id', ondelete='CASCADE'))
)

relatedrecid_identifier = db.Table(
    'relatedrecid_identifier',
    db.Column('submission_id', db.Integer,
              db.ForeignKey('hepsubmission.id')),
    db.Column('relatedrecid_id', db.Integer, db.ForeignKey('relatedrecid.id', ondelete='CASCADE'))
)


class DataSubmission(db.Model):
    """
    The submission object associated with a data table.
    """
    __tablename__ = "datasubmission"

    # id is a unique id for each datasubmission and version
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

    # A list of objects containing DOI values of related tables defined in the submission file.
    related_tables = db.relationship("RelatedTable", secondary="relatedtable_identifier",
                               cascade="all,delete")

    # the record ID for the resulting record created on finalisation.
    associated_recid = db.Column(db.Integer)

    # when a new version is loaded, the version is increased and
    # maintained so people can go back in time
    # through a submissions review stages.
    version = db.Column(db.Integer, default=0)

    def get_related_to_this_datasubmissions(self):
        """
            Get the DataSubmission Objects with a RelatedTable entry
            where this doi is referred to in related_doi.

            :return: [List] List of DataSubmission objects.
        """
        related_submissions = (
            DataSubmission.query.join(RelatedTable, RelatedTable.table_doi == DataSubmission.doi)
            .join(HEPSubmission, HEPSubmission.publication_recid == DataSubmission.publication_recid)
            .filter(RelatedTable.related_doi == self.doi)
            .filter(HEPSubmission.overall_status == 'finished')
            .all()
        )
        return related_submissions

    def get_related_datasubmissions(self):
        """
        Queries the database for all DataSubmission objects contained in
        this object's related DOI list.
        Only returns an object if associated HEPSubmission status is 'finished'
        (All submissions this one is relating to)
        :return: [list] A list of DataSubmission objects
        """
        related_submissions = []
        for related in self.related_tables:
            submission = (
                DataSubmission.query.filter(DataSubmission.doi == related.related_doi)
                          .join(HEPSubmission, HEPSubmission.publication_recid == DataSubmission.publication_recid)
                          .filter(HEPSubmission.overall_status == 'finished')
                          .first())
            if submission:
                related_submissions.append(submission)
        return related_submissions


    def get_table_data_list(self, data_type):
        """
        Generates a list of general information (name, doi, desc) dictionaries of related DataSubmission objects.

        Will either use the related data list (get_related_data_submissions)
        OR the `related to this` list (generated by get_related_to_this_datasubmissions)
        :param str data_type : The flag to decide which relation data to use.
        :return: [list] A list of dictionaries with the name, doi and description of the object.
        """
        # Selects the related data based on the data_type flag
        if data_type == "related":
            data = self.get_related_datasubmissions()
        elif data_type == "related-to-this":
            data = self.get_related_to_this_datasubmissions()

        record_data = []
        for datum in data:
            record_data.append({
                "name": datum.name,
                "doi": datum.doi,
                "description": datum.description
            })
        return record_data


class RelatedTable(db.Model):
    """
    The submission object associated with a related table entry.
    """
    __tablename__ = "relatedtable"
    id = db.Column(db.Integer, primary_key=True, nullable=False,
                autoincrement=True)
    table_doi = db.Column(db.String(128), nullable=True)
    related_doi = db.Column(db.String(128), nullable=True)


class RelatedRecid(db.Model):
    """
    The submission object associated with a related record entry.
    """
    __tablename__ = "relatedrecid"
    id = db.Column(db.Integer, primary_key=True, nullable=False,
                autoincrement=True)
    this_recid = db.Column(db.Integer, nullable=True)
    related_recid = db.Column(db.Integer, nullable=True)


@event.listens_for(db.Session, 'before_flush')
def receive_before_flush(session, flush_context, instances):
    """Listen for the 'before_flush' event to check for DataSubmission
    deletions and ensure related DataResource and DataReview entries are
    loaded by SQLAlchemy before deletion to ensure all cascades, event
    listeners, etc are run."""
    for obj in session.deleted:
        if isinstance(obj, DataSubmission):
            try:
                log.debug("Deleting data resource %s" % obj.data_file)
                dataresource = DataResource.query.filter_by(id=obj.data_file).first()
                if dataresource:
                    db.session.delete(dataresource)
            except Exception as e:
                log.error("Unable to delete data resource with id %s whilst "
                          "deleting data submission id %s. Error was: %s"
                          % (obj.data_file, obj.id, e))

            log.debug("Deleting reviews for data submission %s" % obj.id)
            reviews = DataReview.query.filter_by(data_recid=obj.id).all()
            for review in reviews:
                try:
                    db.session.delete(review)
                except Exception as e:
                    log.error("Unable to delete review with id %s whilst "
                              "deleting data submission id %s. Error was: %s"
                              % (review.id, obj.id, e))


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
    """
    Details of a data resource, which could be a data table, an image, a
    script, a ROOT file, or a link to an external website or GitHub repo.

    Data resources can be related to submissions in various ways:

    - Resources relating to a submission (HEPSubmission.resources) are linked
      via the `data_resource_link` table
    - Data files belonging to a data table (`DataSubmission.data_file`)
      are linked via the `data_file` field of `datasubmission`
    - Resources relating to a data table (`DataSubmission.resources`) are
      linked via the `datafile_identifier` table
    """
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
    doi = db.Column(db.String(128), nullable=True)


@event.listens_for(DataResource, 'after_delete')
def receive_data_resource_after_delete(mapper, connection, target):
    "Delete the file on disk when a DataResource is deleted"
    log.debug("Deleting data resource id %s" % target.id)
    if not target.file_location.lower().startswith('http'):
        if os.path.isfile(target.file_location):
            # Check whether there's another dataresource with the same file
            # location before deleting.
            file_count = DataResource.query.filter_by(
                    file_location=target.file_location
                ).count()
            if file_count == 0:
                log.debug('Deleting file %s' % target.file_location)
                os.remove(target.file_location)
        else:
            log.warning("Could not remove file %s as it is not a valid file." % target.file_location)


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
    data_recid = db.Column(db.Integer,
                           db.ForeignKey("datasubmission.id", ondelete='CASCADE'))

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
