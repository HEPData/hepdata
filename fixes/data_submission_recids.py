# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2022 CERN.
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
import logging

from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db
from sqlalchemy import func

from hepdata.cli import fix
from hepdata.ext.elasticsearch.api import index_record_ids, push_data_keywords
from hepdata.modules.records.utils.common import get_record_by_id
from hepdata.modules.records.utils.doi_minter import generate_dois_for_submission
from hepdata.modules.records.utils.submission import finalise_datasubmission
from hepdata.modules.submission.models import HEPSubmission, DataSubmission

logging.basicConfig()
log = logging.getLogger('data_submission_recids')
log.setLevel('INFO')


@fix.command()
@with_appcontext
def fix_data_submission_recids():
    """Update associated_recids for data submissions with version > 1"""
    submissions_to_update = HEPSubmission.query \
        .filter(HEPSubmission.version > 1) \
        .filter(HEPSubmission.overall_status == 'finished') \
        .order_by(HEPSubmission.publication_recid, HEPSubmission.version).all()

    log.info(f"Updating data submissions for {len(submissions_to_update)} publications with version > 1")

    for i, hep_submission in enumerate(submissions_to_update):
        # We have ordered the results so if this is the last entry in
        # submissions_to_update, or the next entry has a different
        # publication_recid, then this must be the latest version
        is_latest = (i + 1 == len(submissions_to_update)) or \
            submissions_to_update[i+1].publication_recid != hep_submission.publication_recid
        _create_new_data_records(hep_submission, is_latest)

    log.info("Checking for any more duplicate associated rec_ids...")
    duplicates = DataSubmission.query.with_entities(
        DataSubmission.associated_recid,
        func.count(DataSubmission.associated_recid)) \
        .filter(DataSubmission.associated_recid.isnot(None)) \
        .group_by(DataSubmission.associated_recid) \
        .having(func.count(DataSubmission.associated_recid) > 1).all()

    if duplicates:
        log.warning("There are still some records with duplicate associated_recids:")
        for d in duplicates:
            log.warning(f"    associated_recid: {d[0]}, count {d[1]}")
    else:
        log.info('No duplicates found 👍')


def _create_new_data_records(hep_submission, is_latest=True):
    log.info("Checking records for publication rec_id "
             f"{hep_submission.publication_recid}, "
             f"version {hep_submission.version} "
             f"(inspire id {hep_submission.inspire_id})")

    data_submissions = DataSubmission.query.filter_by(
        publication_recid=hep_submission.publication_recid,
        version=hep_submission.version
    )
    # Get full list of associated recids across all versions so we can check
    # for duplicates
    all_versions_associated_recids = [
        x[0] for x in
        db.session.query(DataSubmission.associated_recid)
          .filter_by(publication_recid=hep_submission.publication_recid)
    ]

    generated_record_ids = []
    publication_record = get_record_by_id(hep_submission.publication_recid)
    last_updated = datetime.strftime(
        hep_submission.last_updated,
        '%Y-%m-%d %H:%M:%S'
    )

    for data_submission in data_submissions:
        # Only re-finalise those data submissions whose associated recid is not unique
        if all_versions_associated_recids.count(data_submission.associated_recid) > 1:
            log.info(f"Re-finalising data_submission id {data_submission.id}")
            finalise_datasubmission(
                last_updated,
                {},
                generated_record_ids,
                publication_record,
                hep_submission.publication_recid,
                data_submission,
                data_submission.version
            )

    db.session.commit()

    if generated_record_ids:
        # Only mint DOIs if not testing.
        if not current_app.config.get('TESTING', False):
            generate_dois_for_submission.delay(
                inspire_id=hep_submission.inspire_id,
                version=hep_submission.version
            )

        # Reindex updated data records if this is the latest version
        if is_latest:
            # Check publication is in the index - add it if not
            log.info(f'Indexing record ids: {[hep_submission.publication_recid] + generated_record_ids}')
            index_record_ids([hep_submission.publication_recid] + generated_record_ids)
            push_data_keywords(pub_ids=[hep_submission.publication_recid])
