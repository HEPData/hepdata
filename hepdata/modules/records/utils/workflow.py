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

from datetime import datetime
import uuid

from invenio_pidstore.minters import recid_minter
from invenio_records import Record

from hepdata.modules.permissions.models import SubmissionParticipant
from invenio_db import db

from hepdata.modules.records.utils.common import get_record_by_id

def create_data_structure(ctx):
    """
    The data structures need to be normalised before being stored in
    the database. This is performed here.

    :param ctx: record information as a dictionary
    :return: a cleaned up representation.
    """

    title = ctx.get('title')
    if type(ctx.get('title')) is list and len(ctx.get('title')) > 0:
        title = ctx.get('title')[0]

    first_author = {}
    authors = ctx.get('authors', [])
    if authors is not None and len(authors) > 0:
        first_author = authors[0]

    record = {"title": title,
              "abstract": str(ctx.get('abstract')),
              "inspire_id": ctx.get("inspire_id"),
              "first_author": first_author,
              "authors": authors
              }

    optional_keys = ["related_publication", "recid", "keywords", "dissertation", "type",
                     "control_number", "doi", "creation_date", "year", "hepdata_doi",
                     "last_updated", "data_endpoints", "collaborations",
                     "journal_info", "uploaders", "reviewers", "subject_area", "arxiv_id"]

    for key in optional_keys:
        if key in ctx:
            record[key] = ctx[key]

            if "recid" == key:
                record[key] = ctx[key]

    return record


def update_record(recid, ctx):
    """
    Updates a record given a new dictionary.

    :param recid:
    :param ctx:
    :return:
    """
    print('Updating record {}'.format(recid))
    record = get_record_by_id(recid)
    for key, value in ctx.items():
        record[key] = value
    record["recid"] = recid

    record.commit()
    db.session.commit()

    return record


def create_record(ctx):
    """
    Creates the record in the database.

    :param ctx: The record metadata as a dictionary.
    :return: the recid and the uuid
    """
    record_information = create_data_structure(ctx)
    record_id = uuid.uuid4()
    pid = recid_minter(record_id, record_information)
    record_information['recid'] = int(pid.pid_value)
    record_information['uuid'] = str(record_id)

    Record.create(record_information, id_=record_id)
    db.session.commit()

    return record_information


def update_action_for_submission_participant(recid, user_id, action):
    SubmissionParticipant.query.filter_by(
        publication_recid=recid, role=action, user_account=user_id) \
        .update(dict(action_date=datetime.utcnow()))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
