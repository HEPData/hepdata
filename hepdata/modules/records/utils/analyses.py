# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2021 CERN.
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

import logging

from celery import shared_task
from flask import current_app
from invenio_db import db
import requests

from hepdata.ext.opensearch.api import index_record_ids
from hepdata.modules.submission.api import get_latest_hepsubmission, is_resource_added_to_submission
from hepdata.modules.submission.models import DataResource, HEPSubmission, data_reference_link
from hepdata.utils.users import get_user_from_id
from hepdata.modules.records.subscribers.rest import subscribe
from hepdata.modules.records.subscribers.api import is_current_user_subscribed_to_record
from hepdata.modules.records.utils.common import get_license

logging.basicConfig()
log = logging.getLogger(__name__)


@shared_task
def update_analyses(endpoint=None):
    """
    Update (Rivet, MadAnalysis 5, SModelS, CheckMATE, HackAnalysis and Combine) analyses and remove outdated resources.
    Allow bulk subscription to record update notifications if "subscribe_user_id" in endpoint.
    Add optional "description" and "license" fields if present in endpoint.

    :param endpoint: either "rivet" or "MadAnalysis" or "SModelS" or "CheckMATE" or "HackAnalysis" or "Combine" or None (default) for all
    """
    endpoints = current_app.config["ANALYSES_ENDPOINTS"]
    for analysis_endpoint in endpoints:

        if endpoint and endpoint != analysis_endpoint:
            continue

        if "endpoint_url" in endpoints[analysis_endpoint]:

            log.info("Updating analyses from {0}...".format(analysis_endpoint))

            response = requests.get(endpoints[analysis_endpoint]["endpoint_url"])

            if response and response.status_code == 200:

                analyses = response.json()

                analysis_resources = DataResource.query.filter_by(file_type=analysis_endpoint).all()

                # Check for missing analyses.
                for record in analyses:
                    submission = get_latest_hepsubmission(inspire_id=record, overall_status='finished')

                    if submission:
                        num_new_resources = 0

                        for analysis in analyses[record]:
                            _resource_url = endpoints[analysis_endpoint]["url_template"].format(analysis)

                            if not is_resource_added_to_submission(submission.publication_recid, submission.version,
                                                                   _resource_url):

                                log.info('Adding {} analysis to ins{} with URL {}'.format(
                                    analysis_endpoint, record, _resource_url)
                                )
                                new_resource = DataResource(
                                    file_location=_resource_url,
                                    file_type=analysis_endpoint)

                                if "description" in endpoints[analysis_endpoint]:
                                    new_resource.file_description = str(endpoints[analysis_endpoint]["description"])

                                if "license" in endpoints[analysis_endpoint]:
                                    resource_license = get_license(endpoints[analysis_endpoint]["license"])
                                    new_resource.file_license = resource_license.id

                                submission.resources.append(new_resource)
                                num_new_resources += 1

                            else:

                                # Remove resources from 'analysis_resources' list.
                                resources = list(filter(lambda a: a.file_location == _resource_url, analysis_resources))
                                for resource in resources:
                                    analysis_resources.remove(resource)

                        if num_new_resources:

                            try:
                                db.session.add(submission)
                                db.session.commit()
                                latest_submission = get_latest_hepsubmission(inspire_id=record)
                                if submission.version == latest_submission.version:
                                    index_record_ids([submission.publication_recid])
                            except Exception as e:
                                db.session.rollback()
                                log.error(e)

                    else:
                        log.debug("An analysis is available in {0} but with no equivalent in HEPData (ins{1}).".format(
                            analysis_endpoint, record))

                if analysis_resources:
                    # Extra resources that were not found in the analyses JSON file.
                    # Need to delete extra resources then reindex affected submissions.
                    # Only take action if latest version is finished (most important case).
                    try:
                        recids_to_reindex = []
                        for extra_analysis_resource in analysis_resources:
                            query = db.select([data_reference_link.columns.submission_id]).where(
                                data_reference_link.columns.dataresource_id == extra_analysis_resource.id)
                            results = db.session.execute(query)
                            for result in results:
                                submission_id = result[0]
                            submission = HEPSubmission.query.filter_by(id=submission_id).first()
                            latest_submission = get_latest_hepsubmission(
                                publication_recid=submission.publication_recid, overall_status='finished'
                            )
                            if submission and latest_submission and submission.version == latest_submission.version:
                                log.info('Removing {} analysis with URL {} from submission {} version {}'
                                         .format(analysis_endpoint, extra_analysis_resource.file_location,
                                                 submission.publication_recid, submission.version))
                                db.session.delete(extra_analysis_resource)
                                recids_to_reindex.append(submission.publication_recid)
                        db.session.commit()
                        if recids_to_reindex:
                            index_record_ids(list(set(recids_to_reindex)))  # remove duplicates before indexing
                    except Exception as e:
                        db.session.rollback()
                        log.error(e)

                # Allow bulk subscription to record update notifications.
                if "subscribe_user_id" in endpoints[analysis_endpoint]:
                    user = get_user_from_id(endpoints[analysis_endpoint]["subscribe_user_id"])
                    if user:
                        for record in analyses:
                            submission = get_latest_hepsubmission(inspire_id=record, overall_status='finished')
                            if submission and not is_current_user_subscribed_to_record(submission.publication_recid, user):
                                subscribe(submission.publication_recid, user)

        else:
            log.debug("No endpoint url configured for {0}".format(analysis_endpoint))
