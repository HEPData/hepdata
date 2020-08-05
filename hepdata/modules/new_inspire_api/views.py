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

"""Get publication information using new INSPIRE API."""

from copy import deepcopy

from flask import request, Blueprint, jsonify
from hepdata.modules.records.utils.common import record_exists
from hepdata.resilient_requests import resilient_requests
from hepdata.modules.new_inspire_api.parser import parsed_content_defaults, get_title, get_doi, get_authors, get_type, get_abstract, \
    get_creation_date, get_arxiv_id, get_collaborations, get_keywords, get_journal_info, get_year, get_subject_area, updated_parsed_content_for_thesis

import logging

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint('inspire_datasource', __name__, url_prefix='/inspire')


def get_inspire_record_information(inspire_rec_id):
    url = 'https://inspirehep.net/api/literature/{}'.format(inspire_rec_id)
    log.debug('Looking up: ' + url)
    req = resilient_requests('get', url)
    status = req.status_code

    if status == 200:
        content = req.json()

        parsed_content = {
            'title': get_title(content['metadata']),
            'doi': get_doi(content['metadata']),
            'authors': get_authors(content['metadata']),
            'type': get_type(content['metadata']),
            'abstract': get_abstract(content['metadata']),
            'creation_date': get_creation_date(content['metadata']),
            'arxiv_id': get_arxiv_id(content['metadata']),
            'collaborations': get_collaborations(content['metadata']),
            'keywords': get_keywords(content['metadata']),
            'journal_info': get_journal_info(content['metadata']),
            'year': get_year(content['metadata']),
            'subject_area': get_subject_area(content['metadata']),
        }

        if 'thesis' in parsed_content['type'] and 'thesis_info' in content['metadata'].keys():
            parsed_content = updated_parsed_content_for_thesis(content, parsed_content)
        elif 'thesis' in parsed_content['type'] and 'thesis_info' not in content['metadata'].keys():
            parsed_content['dissertation'] = {}

        status = 'success'

    else:
        parsed_content = deepcopy(parsed_content_defaults)

    return parsed_content, status


@blueprint.route('/search', methods=['GET'])
def get_record_from_inspire():
    if 'id' not in request.args:
        return jsonify({'status': 'no inspire id provided'})

    inspire_id = request.args['id']

    content, status = get_inspire_record_information(inspire_id)

    # check that id is not present already.
    exists = record_exists(inspire_id=inspire_id)
    if exists:
        status = 'exists'

    return jsonify({'source': 'inspire',
                    'id': inspire_id,
                    'query': content,
                    'status': status})
