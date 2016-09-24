#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

"""Common utilites used across the code base"""
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.models import HEPSubmission


def get_latest_hepsubmission(*args, **kwargs):
    """
    Gets of creates a new HEPSubmission record
    :param recid: the publication record id
    :param coordinator: the user id of the user who owns this record
    :param status: e.g. todo, finished.
    :return: the newly created HEPSubmission object
    """

    if 'inspire_id' in kwargs:
        hepsubmissions = HEPSubmission.query.filter_by(inspire_id=kwargs.pop('inspire_id')).all()

    if 'recid' in kwargs:
        hepsubmissions = HEPSubmission.query.filter_by(publication_recid=kwargs.pop('recid')).all()

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
