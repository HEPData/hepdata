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
from flask import Blueprint, request, render_template, jsonify
from hepdata.config import CFG_DATA_KEYWORDS
from hepdata.ext.elasticsearch.api import search as es_search, \
    search_authors as es_search_authors
from hepdata.utils.url import modify_query
from config import HEPDATA_CFG_MAX_RESULTS_PER_PAGE, HEPDATA_CFG_FACETS

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
    if 'date' in args:
        date = args['date']
        if date.isdigit() and int(date) > 0:
            args['date'] = int(date)
        else:
            del args['date']


def sort_facets(facets):
    """ Sort the facets in an arbitrary way that we think is appropriate. """
    order = {
        'collaboration': 1,
        'date': 2,
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
    check_date(args)
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
    }


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

    ctx = {
        'results': query_result['results'],
        'total_hits': query_result['total'],
        'facets': facets,
        'q': query_params['q'],
        'modify_query': modify_query,
        'max_results': query_params['size'],
        'pages': {'current': query_params['current_page'],
                  'total': total_pages},
        'filters': dict(query_params['filters']),
    }

    return render_template('search_results.html', ctx=ctx)
