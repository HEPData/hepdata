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
from __future__ import division

import json

import sys
from flask import Blueprint, request, render_template, jsonify
from hepdata.config import CFG_DATA_KEYWORDS
from hepdata.ext.elasticsearch.api import search as es_search, \
    search_authors as es_search_authors
from hepdata.modules.records.utils.common import decode_string
from hepdata.utils.url import modify_query
from config import HEPDATA_CFG_MAX_RESULTS_PER_PAGE, HEPDATA_CFG_FACETS
from flask import session

blueprint = Blueprint('es_search',
                      __name__,
                      url_prefix='/search',
                      template_folder='templates',
                      static_folder='static')


def calculate_total_pages(query_result, max_results):
    """ Calculate the overall number of pages of results
    given the number of hits and max number of records displayed per page """
    total_pages = query_result['total'] // max_results
    if not query_result['total'] % max_results == 0:
        total_pages += 1
    return total_pages


def check_page(args):
    """ Get the page query parameter from the URL and if it doesn't exist
    assign a default value. """
    page = args.get('page', '1')
    try:
        page = int(page)
        if page < 1:
            raise ValueError
    except ValueError:
        page = 1

    args['page'] = page


def check_max_results(args):
    """ Get the size query parameter from the URL and if it doesn't exist
    assign a default value. """
    max_results = args.get('size', HEPDATA_CFG_MAX_RESULTS_PER_PAGE)
    try:
        max_results = int(max_results)
        if max_results < 1:
            raise ValueError
    except ValueError:
        max_results = HEPDATA_CFG_MAX_RESULTS_PER_PAGE

    args['size'] = max_results


def check_date(args):
    """ Get the date parameter from the URL and if it doesn't exist
    assign a default value. """
    min_date = sys.maxsize
    max_date = sys.maxsize * -1

    if 'date' in args:
        if args['date'] is not '':
            dates = args['date'].split(',')
            min_date = int(dates[0])
            max_date = min_date
            if len(dates) > 1:
                max_date = int(dates[1])
            years = []
            if len(dates)==1 or dates[0] == dates[1]:
                years = [min_date]
            else:
                for year in range(min_date, max_date):
                    years.append(year)
            args['date'] = years

        else:
           del args['date']

    return min_date, max_date


def sort_facets(facets):
    """ Sort the facets in an arbitrary way that we think is appropriate. """
    order = {
        'date': 1,
        'collaboration': 2,
        'reactions': 3,
        'observables': 4,
        'cmenergies': 5,
        'author': 6
    }
    facets = sorted(facets, key=lambda x: order[x['type']])

    return facets


def filter_facets(facets, total_hits):
    """ For the data keywords, show only the ones with >10 count,
    if there is more than 100 hits altogether. Filter out the empty ones. """
    HITS = 100
    THRESHOLD = 10

    if total_hits > HITS:
        keyword_facets = [f for f in facets if f['type'] in CFG_DATA_KEYWORDS]
        for facet in keyword_facets:
            vals = [v for v in facet['vals'] if v['doc_count'] >= THRESHOLD]
            facet['vals'] = vals

    nonempty_facets = [kf for kf in facets if len(kf['vals']) > 0]

    return nonempty_facets


def parse_query_parameters(request_args):
    """ Get query parameters from the request and preprocess them.

    :param [dict-like structure] Any structure supporting get calls
    :result [dict] Parsed parameters"""

    args = {key: value[0] for (key, value) in dict(request_args).iteritems()}
    min_date, max_date = check_date(args)
    check_page(args)
    check_max_results(args)

    filters = []
    for filter in HEPDATA_CFG_FACETS:
        if filter in args:
            filters.append((filter, args[filter]))

    return {
        'q': args.get('q', ''),
        'sorting_field': args.get('sort_by', ''),
        'sorting_order': args.get('sort_order', ''),
        'size': args['size'],
        'current_page': args['page'],
        'offset': (args['page'] - 1) * args['size'],
        'filters': filters,
        'min_date': min_date,
        'max_date': max_date
    }


def set_session_item(key, value):
    """
    Stores a key and value in the session.
    By default we use REDIS
    :param key: e.g. my_key
    :param value: anything, dict, array, string, int, etc.
    :return: 'ok'
    """
    session[key] = value
    return 'ok'


def get_session_item(key):
    return session.get(key, [])


@blueprint.route('/authors', methods=['GET', 'POST'])
def search_authors():
    author_name = request.args.get('q', '')
    results = es_search_authors(author_name)
    return jsonify({'results': results})


@blueprint.route('/', methods=['GET', 'POST'])
def search():
    """ Main search endpoint.
    Parse the request, perform search and show the results """
    query_params = parse_query_parameters(request.args)

    query_result = es_search(query_params['q'],
                             filters=query_params['filters'],
                             size=query_params['size'],
                             sort_field=query_params['sorting_field'],
                             sort_order=query_params['sorting_order'],
                             offset=query_params['offset'])

    total_pages = calculate_total_pages(query_result, query_params['size'])

    if query_params['current_page'] > total_pages:
        query_params['current_page'] = total_pages

    facets = filter_facets(query_result['facets'], query_result['total'])
    facets = sort_facets(facets)

    url_path = modify_query('.search', **{'date': None})
    year_facet = get_session_item(url_path)
    if len(year_facet) == 0:
        for facet in facets:
            if facet['printable_name'] is 'Date':
                year_facet = {decode_string(json.dumps(facet['vals']))}
                set_session_item(url_path, year_facet)
                break

    ctx = {
        'results': query_result['results'],
        'total_hits': query_result['total'],
        'facets': facets,
        'year_facet': list(year_facet)[0],
        'q': query_params['q'],
        'modify_query': modify_query,
        'max_results': query_params['size'],
        'pages': {'current': query_params['current_page'],
                  'total': total_pages},
        'filters': dict(query_params['filters']),
    }

    if query_params['min_date'] is not sys.maxsize:
        ctx['min_year'] = query_params['min_date']
        ctx['max_year'] = query_params['max_date']

    return render_template('search_results.html', ctx=ctx)
