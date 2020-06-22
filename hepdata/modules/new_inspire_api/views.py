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


def get_inspire_record_information(inspire_rec_id, verbose=False):
    url = 'http://inspirehep.net/api/literature/{}'.format(inspire_rec_id)
    if verbose:
        print('\rLooking up: ' + url)
    req = requests.get(url)
    content = req.json()
    status = req.status_code

    if content and status != 404:
        parsed_content = {
            'title': content['metadata']['titles'][0]['title'],
            'doi': (content['metadata']['dois'][-1]['value'] if 'dois' in content['metadata'] and len(content['metadata']['dois']) > 0 else None),
            'authors': [{'affiliation': (author['affiliations'][0]['value'] if 'affiliations' in author.keys() else ''),
                         'full_name': author['full_name']} for author in content['metadata']['authors']],
            'type': content['metadata']['document_type'],
            'abstract': (content['metadata']['abstracts'][-1]['value'] if 'abstracts' in content['metadata'].keys() else None),
            'creation_date': (expand_date(content['metadata']['preprint_date']) if 'preprint_date' in content['metadata'].keys() else
                              content['metadata']['legacy_creation_date'] if 'legacy_creation_date' in content['metadata'] else None),
            'arxiv_id': ('arXiv:' + content['metadata']['arxiv_eprints'][-1]['value'] if 'arxiv_eprints' in content['metadata'].keys() else None),
            'collaborations': ([collaboration['value'] for collaboration in content['metadata']['collaborations']] if 'collaborations' in content['metadata'] else []),
            'keywords': content['metadata']['keywords'] if 'keywords' in content['metadata'].keys() else [],
            'journal_info': (((content['metadata']['publication_info'][0]['journal_title'] + ' ' if 'journal_title' in content['metadata']['publication_info'][0] else '') +
                              content['metadata']['publication_info'][0]['journal_volume'] +
                              ' (' + str(content['metadata']['publication_info'][0]['year']) + ') ' + (
                                  content['metadata']['publication_info'][0]['artid'] if 'artid' in content['metadata']['publication_info'][0].keys() else
                                  content['metadata']['publication_info'][0]['page_start'] + "-" + content['metadata']['publication_info'][0]['page_end'] if
                                  'page_start' in content['metadata']['publication_info'][0].keys() and 'page_end' in content['metadata']['publication_info'][0].keys() else ''))
                             if ('publication_info' in content['metadata'] and len(content['metadata']['publication_info']) > 0 and
                                 all(keyword in content['metadata']['publication_info'][0].keys() for keyword in ['journal_volume', 'year'])) else
                             content['metadata']['publication_info'][0]['pubinfo_freetext'] if ('publication_info' in content['metadata'] and
                                                                                                len(content['metadata']['publication_info']) > 0 and
                                                                                                type(content['metadata']['publication_info'][0]) is dict and
                                                                                                'pubinfo_freetext' in content['metadata']['publication_info'][0].keys()) else
                             content['metadata']['publication_info'] if 'publication_info' in content['metadata'].keys() else 'No Journal Information'),
            'year': (str(content['metadata']['publication_info'][-1]['year']) if ('publication_info' in content['metadata'] and 'year' in content['metadata']['publication_info'][-1].keys())
                     else content['metadata']['preprint_date'].split("-")[0] if 'preprint_date' in content['metadata'].keys() else
                     content['metadata']['legacy_creation_date'].split("-")[0] if 'legacy_creation_date' in content['metadata'] else None),
            'subject_area': (content['metadata']['arxiv_eprints'][-1]['categories'] if 'arxiv_eprints' in content['metadata'].keys() else
                             [entry['term'] for entry in content['metadata']['inspire_categories'] if 'term' in entry.keys()] if ('inspire_categories' in content['metadata'].keys() and
                             len(content['metadata']['inspire_categories']) > 0) else[]),
        }
        if 'thesis' in parsed_content['type'] and 'thesis_info' in content['metadata'].keys():
            parsed_content['dissertation'] = content['metadata']['thesis_info']
            if ('institutions' in parsed_content['dissertation'].keys() and
               len(parsed_content['dissertation']['institutions']) == 1 and
               'name' in parsed_content['dissertation']['institutions'][0]):
                parsed_content['dissertation']['institution'] = parsed_content['dissertation']['institutions'][0]['name']
                parsed_content['dissertation'].pop('institutions')
            if 'date' in content['metadata']['thesis_info'].keys():
                parsed_content['year'] = content['metadata']['thesis_info']['date']
                if parsed_content['year'] is not None:
                    if content['metadata']['legacy_creation_date'][:4] == parsed_content['year']:
                        parsed_content['creation_date'] = content['metadata']['legacy_creation_date']
                    else:
                        parsed_content['creation_date'] = expand_date(parsed_content['year'])
            if 'degree_type' in parsed_content['dissertation'].keys():
                parsed_content['dissertation']['type'] = parsed_content['dissertation'].pop('degree_type')
            if 'type' in parsed_content['dissertation'].keys() and parsed_content['dissertation']['type'] == "phd":
                parsed_content['dissertation']['type'] == "PhD"
            if 'date' in parsed_content['dissertation'].keys():
                parsed_content['dissertation']['defence_date'] = parsed_content['dissertation'].pop('date')
        elif 'thesis' in parsed_content['type'] and 'thesis_info' not in content['metadata'].keys():
            parsed_content['dissertation'] = {}
        status = 'success'
    else:
        parsed_content = {
            'title': None,
            'doi': None,
            'authors': None,
            'type': [],
            'abstract': None,
            'creation_date': None,
            'arxiv_id': None,
            'collaborations': [],
            'keywords': [],
            'journal_info': 'No Journal Information',
            'year': None,
            'subject_area': [],
        }
        status = 'success'

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
    if value == '':
        return value

    date_parts = value.split('-')

    if len(date_parts) == 1:
        date_parts.append('01')
    if len(date_parts) == 2:
        date_parts.append('01')
    return "-".join(date_parts)
