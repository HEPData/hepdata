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
import logging

from invenio_db import db
from hepdata.modules.submission.models import DataResource, SubmissionObserver
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.models import HEPSubmission

"""Common utilities used across the code base."""

logging.basicConfig()
log = logging.getLogger(__name__)


def is_resource_added_to_submission(recid, version, resource_url):
    """
    Returns if a submission already has the given resource url
    :param recid:
    :param version:
    :param resource_url:
    :return:
    """
    return HEPSubmission.query.filter(HEPSubmission.publication_recid == recid,
                                      HEPSubmission.version == version,
                                      HEPSubmission.resources.any(
                                          DataResource.file_location == resource_url)).count() > 0


def get_latest_hepsubmission(*args, **kwargs):
    """
    Gets the latest HEPSubmission record matching the given kwargs

    :return: the HEPSubmission object or None
    """

    hepsubmissions = HEPSubmission.query.filter_by(**kwargs).all()

    last = None
    for hepsubmission in hepsubmissions:
        if last is None:
            last = hepsubmission
        else:
            if hepsubmission.version > last.version:
                last = hepsubmission

    return last


def get_submission_participants_for_record(publication_recid, roles=None, **kwargs):
    """Gets the participants for a given publication record id

    :param int publication_recid: publication_recid of a submission.
    :param ``**kwargs``: Additional filter parameters to pass to `filter_by`.
    :return: List of participants relating to that record
    :rtype: list[SubmissionParticipant]
    """
    query = SubmissionParticipant.query.filter_by(
            publication_recid=publication_recid,
            **kwargs
    )

    if roles:
        query = query.filter(SubmissionParticipant.role.in_(roles))

    return query.all()


def get_primary_submission_participants_for_record(publication_recid):
    submission_participants = get_submission_participants_for_record(publication_recid, status="primary")
    return submission_participants


def get_or_create_submission_observer(publication_recid, regenerate=False):
    """
    Gets or re/generates a SubmissionObserver key for a given recid.
    Where an observer does not exist for a recid (with existing sub),
    it is created and returned instead.

    :param publication_recid: The publication record id
    :param regenerate: Whether to regenerate/force generate the key
    :return: SubmissionObserver key, created, or None
    """
    submission_observer = SubmissionObserver.query.filter_by(publication_recid=publication_recid).first()
    created = False

    if submission_observer is None:
        submission = get_latest_hepsubmission(publication_recid=publication_recid)
        if submission:
            if submission.overall_status == "todo" or regenerate:
                submission_observer = SubmissionObserver(publication_recid=publication_recid)
                created = True
        else:
            # No submission, no observer, return None
            return None

    # If we are to regenerate, and SubmissionObserver was queried and not generated.
    # If just created, we don't need to generate anything.
    if not created and regenerate:
        submission_observer.generate_observer_key()

    # Only commit if we have created or regenerated
    if created or regenerate:
        db.session.add(submission_observer)
        db.session.commit()

    return submission_observer


def delete_submission_observer(recid):
    """
    Deletes a SubmissionObserver object from the database
    based on a given recid value.

    :param: recid: int - The recid to delete on
    """

    # Validate recid is an integer
    try:
        recid = int(recid)
    except (ValueError, TypeError) as e:
        log.error(f"Invalid recid provided for observer deletion: {recid}")
        raise ValueError(f"Supplied recid value ({recid}) for deletion is not an Integer.") from e

    try:
        submission_observer = SubmissionObserver.query.filter_by(publication_recid=recid).first()

        if submission_observer:
            db.session.delete(submission_observer)
            db.session.commit()
            log.info(f"Deleted observer for submission {recid}")
    except Exception as e:
        log.error(f"Error deleting observer for submission {recid}: {e}")
        db.session.rollback()
        raise
