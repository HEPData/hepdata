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

from hepdata.ext.elasticsearch.api import index_record_ids
from hepdata.modules.submission.api import get_latest_hepsubmission, \
    is_resource_added_to_submission
from hepdata.modules.submission.models import DataResource

logging.basicConfig()
log = logging.getLogger(__name__)


@shared_task
def update_analyses():
    endpoints = current_app.config["ANALYSES_ENDPOINTS"]
    for analysis_endpoint in endpoints:

        if "endpoint_url" in endpoints[analysis_endpoint]:

            log.info("Updating analyses from {0}...".format(analysis_endpoint))

            response = requests.get(endpoints[analysis_endpoint]["endpoint_url"])

            if response:

                analyses = response.json()

                for record in analyses:
                    submission = get_latest_hepsubmission(inspire_id=record, overall_status='finished')

                    if submission:
                        num_new_resources = 0

                        for analysis in analyses[record]:
                            _resource_url = endpoints[analysis_endpoint]["url_template"].format(analysis)
                            if not is_resource_added_to_submission(submission.publication_recid, submission.version,
                                                                   _resource_url):
                                print('Adding {} analysis to ins{} with URL {}'
                                      .format(analysis_endpoint, record, _resource_url))
                                new_resource = DataResource(
                                    file_location=_resource_url,
                                    file_type=analysis_endpoint)

                                submission.resources.append(new_resource)
                                num_new_resources += 1

                        if num_new_resources:

                            try:
                                db.session.add(submission)
                                db.session.commit()
                                index_record_ids([submission.publication_recid])
                            except Exception as e:
                                db.session.rollback()
                                log.error(e)

                    else:
                        log.debug("An analysis is available in {0} but with no equivalent in HEPData (ins{1}).".format(
                            analysis_endpoint, record))
        else:
            log.debug("No endpoint url configured for {0}".format(analysis_endpoint))
