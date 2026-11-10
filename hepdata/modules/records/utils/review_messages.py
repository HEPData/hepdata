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

"""Utilities for review conversation retrieval/archival."""

import json

from collections import OrderedDict

from hepdata.modules.records.utils.common import default_time
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataReview, DataSubmission
from hepdata.utils.users import get_user_from_id


def get_review_messages_for_publication(publication_recid, version=None):
    """Return review messages grouped by table name for a publication/version."""
    messages = OrderedDict()

    if version is None:
        latest_submission = get_latest_hepsubmission(publication_recid=publication_recid)
        if not latest_submission:
            return messages
        version = latest_submission.version

    reviews = DataReview.query.filter_by(
        publication_recid=publication_recid, version=version
    ).order_by(DataReview.id.asc()).all()

    for data_review in reviews:
        data_submission = DataSubmission.query.filter_by(id=data_review.data_recid).first()
        if not data_submission:
            continue

        if data_submission.name not in messages:
            messages[data_submission.name] = []

        if data_review.messages:
            data_messages = data_review.messages
            data_messages.sort(key=lambda data_message: data_message.id, reverse=True)
            for data_message in data_messages:
                current_user_obj = get_user_from_id(data_message.user)
                messages[data_submission.name].append(
                    {"message": data_message.message,
                     "user": current_user_obj.email,
                     "post_time": data_message.creation_date}
                )

    return messages


def has_review_messages(messages):
    """Return True if any table has at least one message."""
    return any(len(table_messages) > 0 for table_messages in messages.values())


def serialise_review_messages(messages):
    """Convert datetime fields in messages to JSON-serialisable values."""
    return json.loads(json.dumps(messages, default=default_time))
