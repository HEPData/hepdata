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

from hepdata.modules.submission.models import DataResource
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.models import HEPSubmission

"""Common utilities used across the code base."""


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


def get_submission_participants_for_record(publication_recid):
    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=publication_recid, status="primary").all()

    return submission_participants
