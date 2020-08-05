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

"""Get publication information using old INSPIRE API."""

import requests
from bs4 import BeautifulSoup
from flask import request, Blueprint, jsonify

from hepdata.modules.records.utils.common import record_exists
from .marcxml_parser import get_doi, get_title, get_authors, get_abstract, \
    get_arxiv, get_collaborations, get_keywords, get_date, get_journal_info, get_year, get_collection, \
    get_dissertation, expand_date, get_subject_areas

import logging

logging.basicConfig()
log = logging.getLogger(__name__)

blueprint = Blueprint('inspire_datasource', __name__, url_prefix='/inspire')


def get_inspire_record_information(inspire_rec_id):
    url = 'http://old.inspirehep.net/record/{0}/export/xm'.format(inspire_rec_id)
    log.debug('Looking up: ' + url)
    req = requests.get(url)
    content = req.content
    status = req.status_code

    if content:
        soup = BeautifulSoup(content, "lxml")

        collection_type = get_collection(soup)

        journal_info, year = get_journal_info(soup)
        creation_date, creation_year = get_date(soup)

        if year is None:
            year = get_year(soup)

        if year is None:
            year = creation_year

        content = {
            'title': get_title(soup),
            'doi': get_doi(soup),
            'authors': get_authors(soup),
            'type': get_collection(soup),
            'abstract': get_abstract(soup),
            'creation_date': creation_date,
            'arxiv_id': get_arxiv(soup),
            'collaborations': get_collaborations(soup),
            'keywords': get_keywords(soup),
            'journal_info': journal_info,
            'year': year,
            'subject_area': get_subject_areas(soup)
        }

        if 'thesis' in collection_type:
            dissertation = get_dissertation(soup)
            content['dissertation'] = dissertation
            if year is None:
                content['year'] = dissertation.get('defense_date', None)
                if content['year'] is not None:
                    content['creation_date'] = expand_date(content['year'])

        status = 'success'

    return content, status


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
