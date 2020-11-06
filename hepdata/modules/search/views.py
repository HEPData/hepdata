#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
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
"""HEPData Search Views."""

import json

import sys
from flask import Blueprint, request, render_template, jsonify
from hepdata.config import CFG_DATA_KEYWORDS
from hepdata.ext.elasticsearch.api import search as es_search, \
    search_authors as es_search_authors
from hepdata.modules.records.utils.common import decode_string
from hepdata.utils.session import get_session_item, set_session_item
from hepdata.utils.url import modify_query
from .config import HEPDATA_CFG_MAX_RESULTS_PER_PAGE, HEPDATA_CFG_FACETS

blueprint = Blueprint('es_search',
                      __name__,
                      url_prefix='/search',
                      template_folder='templates',
                      static_folder='static')


def calculate_total_pages(query_result, max_results):
    """
    Calculate the overall number of pages of results
    given the number of hits and max number of records displayed per page.
    """
    total_hits = query_result['total']
    total_pages = total_hits // max_results
    if not total_hits % max_results == 0:
        total_pages += 1
    return total_pages


def check_page(args):
    """
    Get the page query parameter from the URL and if it doesn't exist
    assign a default value.
    """
    page = args.get('page', '1')
    try:
        page = int(page)
        if page < 1:
            raise ValueError
    except ValueError:
        page = 1

    args['page'] = page


def check_max_results(args):
    """
    Get the size query parameter from the URL and if it doesn't exist
    assign a default value.
    """
    max_results = args.get('size', HEPDATA_CFG_MAX_RESULTS_PER_PAGE)
    try:
        max_results = int(max_results)
    except ValueError:
        max_results = HEPDATA_CFG_MAX_RESULTS_PER_PAGE

    if max_results < 1 or max_results > 200:
        max_results = 200 if max_results > 200 else HEPDATA_CFG_MAX_RESULTS_PER_PAGE

    args['size'] = max_results


def check_date(args):
    """
    Get the date parameter from the URL and if it doesn't exist
    assign a default value.
    """
    min_date = sys.maxsize
    max_date = sys.maxsize * -1

    if 'date' in args:
        date_length = len(args['date'])
        if date_length == 4 or date_length == 9:
            if args['date'] is not '':
                dates = args['date'].split(',')

                min_date = int(dates[0])
                max_date = min_date
                if len(dates) > 1:
                    max_date = int(dates[1])
                years = []
                if len(dates) == 1 or dates[0] == dates[1]:
                    years = [min_date]
                else:
                    for year in range(min_date, max_date + 1):
                        years.append(year)
                args['date'] = years

        else:
            del args['date']

    return min_date, max_date


def check_cmenergies(args):
    """
    Get the cmenergues query parameter from the URL and convert to floats
    """
    cmenergies = args.get('cmenergies', None)
    if cmenergies:
        try:
            cmenergies = [float(x) for x in cmenergies.split(',', 1)]
            args['cmenergies'] = cmenergies

        except ValueError:
            del args['cmenergies']


def sort_facets(facets):
    """Sort the facets in an arbitrary way that we think is appropriate."""
    order = {
        'date': 1,
        'collaboration': 2,
        'subject_areas': 3,
        'phrases': 4,
        'reactions': 5,
        'observables': 6,
        'cmenergies': 7,
        'author': 8
    }
    facets = sorted(facets, key=lambda x: order[x['type']])
    return facets


def filter_facets(facets, total_hits):
    """
    For the data keywords, show only the ones with >10 count,
    if there is more than 100 hits altogether. Filter out the empty ones.
    """
    HITS = 50
    THRESHOLD = 10

    if total_hits > HITS:
        keyword_facets = [f for f in facets if f['type'] in CFG_DATA_KEYWORDS]
        for facet in keyword_facets:
            vals = [v for v in facet['vals'] if v['doc_count'] is None or v['doc_count'] >= THRESHOLD]
            facet['vals'] = vals

    nonempty_facets = [kf for kf in facets if len(kf['vals']) > 0]

    return nonempty_facets


def parse_query_parameters(request_args):
    """
    Get query parameters from the request and preprocess them.

    :param request_args: [dict-like structure] Any structure supporting get calls
    :result: [dict] Parsed parameters
    """
    args = dict(request_args)
    min_date, max_date = check_date(args)
    check_cmenergies(args)
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


@blueprint.route('/authors', methods=['GET', 'POST'])
def search_authors():
    author_name = request.args.get('q', '')
    results = es_search_authors(author_name)
    return jsonify({'results': results})


def get_facet(facets, facet_name):
    for facet in facets:
        if facet['printable_name'] is facet_name:
            return facet['vals']
    return None


def process_year_facet(request, facets):
    url_path = modify_query('.search', **{'date': None})
    year_facet = get_session_item(url_path)
    if len(year_facet) == 0 or (request.full_path[:-1] == url_path or request.full_path == url_path):
        # we update the facet if there is no value stored in the session,
        # or if the base url is the same as the stripped url
        year_facet = get_facet(facets, 'Date')
        if year_facet:
            year_facet = {decode_string(json.dumps(year_facet))}
            set_session_item(url_path, year_facet)

    if year_facet and len(year_facet) > 0:
        year_facet = list(year_facet)[0]

    return year_facet


@blueprint.route('/', methods=['GET', 'POST'])
def search():
    """
    Main search endpoint.
    Parse the request, perform search and show the results.
    """
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

    year_facet = process_year_facet(request, facets)

    if ('format' in request.args and request.args['format'] == 'json') \
        or 'json' in request.headers.get('accept', ''):
        query_result['hits'] = {'total': query_result['total']}
        return jsonify(query_result)
    else:
        ctx = {
            'results': query_result['results'],
            'total_hits': query_result['total'],
            'facets': facets,
            'year_facet': year_facet,
            'q': query_params['q'],
            'max_results': query_params['size'],
            'pages': {'current': query_params['current_page'],
                      'total': total_pages,
                      'endpoint': '.search'},
            'filters': dict(query_params['filters']),
        }

        if query_params['min_date'] is not sys.maxsize:
            ctx['min_year'] = query_params['min_date']
            ctx['max_year'] = query_params['max_date']

        ctx['modify_query'] = modify_query

        return render_template('hepdata_search/search_results.html', ctx=ctx)
