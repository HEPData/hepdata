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


import requests

from flask import request, Blueprint, jsonify
from hepdata.modules.records.utils.common import record_exists

blueprint = Blueprint('inspire_datasource', __name__, url_prefix='/inspire')


def get_inspire_record_information(inspire_rec_id):
    url = 'http://inspirehep.net/api/literature/{}'.format(inspire_rec_id)
    print('Looking up: ' + url)
    req = requests.get(url)
    content = req.json()
    status = req.status_code

    if content and status != 404:
        parsed_content = {
            'title': content['metadata']['titles'][0]['title'],
            'doi': (content['metadata']['dois'][-1]['value'] if 'dois' in content['metadata'] and len(content['metadata']['dois']) > 0 else None),
            'authors': [{'affiliations': [affiliation['value'] for affiliation in author['affiliations']], 'full_name': author['full_name']} for author in content['metadata']['authors']],
            'type': content['metadata']['document_type'][0],
            'abstract': (content['metadata']['abstracts'][-1]['value'] if 'abstracts' in content['metadata'].keys() else None),
            'creation_date': (expand_date(content['metadata']['preprint_date']) if 'preprint_date' in content['metadata'].keys() else
                              content['metadata']['legacy_creation_date'] if 'legacy_creation_date' in content['metadata'] else None),
            'arxiv_id': ('arXiv:' + content['metadata']['arxiv_eprints'][-1]['value'] if 'arxiv_eprints' in content['metadata'].keys() else None),
            'collaborations': ([collaboration['value'] for collaboration in content['metadata']['collaborations']] if 'collaborations' in content['metadata'] else None),
            'keywords': content['metadata']['keywords'],
            'journal_info': ((content['metadata']['publication_info'][0]['journal_title'] + ' ' + content['metadata']['publication_info'][0]['journal_volume'] +
                              ' (' + str(content['metadata']['publication_info'][0]['year']) + ') ' + content['metadata']['publication_info'][0]['artid'])
                             if ('publication_info' in content['metadata'] and len(content['metadata']['publication_info']) > 0 and
                                 all(keyword in content['metadata']['publication_info'][0].keys() for keyword in ['journal_title', 'journal_volume', 'year', 'artid'])) else
                             content['metadata']['publication_info'] if 'publication_info' in content['metadata'] else None),
            'year': (content['metadata']['publication_info'][-1]['year'] if ('publication_info' in content['metadata'] and 'year' in content['metadata']['publication_info'][-1].keys())
                     else content['metadata']['preprint_date'].split("-")[0] if 'preprint_date' in content['metadata'].keys() else
                     content['metadata']['legacy_creation_date'].split("-")[0] if 'legacy_creation_date' in content['metadata'] else None),
            'subject_area': (content['metadata']['arxiv_eprints'][-1]['categories'] if 'arxiv_eprints' in content['metadata'].keys() else None),
        }
        if 'thesis' == parsed_content['type'] and 'thesis_info' in content['metadata'].keys():
            content['dissertation'] = content['metadata']['thesis_info']
            if 'date' in content['metadata']['thesis_info'].keys():
                parsed_content['year'] = content['metadata']['thesis_info']['date']
                if parsed_content['year'] is not None:
                    parsed_content['creation_date'] = expand_date(parsed_content['year'])
        status = 'success'
    else:
        parsed_content = content

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


def expand_date(value):
    """
    In the case where the date is not completely
    formed, we need to expand it out.
    so 2012-08 will be 2012-08-01
    and 2012 will be 2012-01-01.
    If nothing, we do nothing.

    :param value:
    :return:
    """
    if value is '':
        return value

    date_parts = value.split('-')

    if len(date_parts) == 1:
        date_parts.append('01')
    if len(date_parts) == 2:
        date_parts.append('01')
    return "-".join(date_parts)
