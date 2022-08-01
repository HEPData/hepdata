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
import datetime
import json
import sys

from flask import Blueprint, request, render_template, jsonify
from hepdata.config import CFG_DATA_KEYWORDS
from hepdata.ext.opensearch.api import search as es_search, \
    search_authors as es_search_authors, get_all_ids as es_get_all_ids
from hepdata.modules.records.utils.common import decode_string
from hepdata.modules.records.api import get_all_ids as db_get_all_ids
from hepdata.utils.session import get_session_item, set_session_item
from hepdata.utils.url import modify_query
from .config import HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE, HEPDATA_CFG_FACETS
from .config import LIMIT_MAX_RESULTS_PER_PAGE

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
    max_results = args.get('size', HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE)
    try:
        max_results = int(max_results)
    except ValueError:
        max_results = HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE

    if max_results < 1:
        max_results = HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE
    elif max_results > LIMIT_MAX_RESULTS_PER_PAGE:
        max_results = LIMIT_MAX_RESULTS_PER_PAGE

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
            if args['date']:
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
    Get the cmenergies query parameter from the URL and convert to floats
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

    if ('format' in request.args and request.args['format'] == 'json') \
            or 'json' in request.headers.get('accept', ''):
        query_result['hits'] = {'total': query_result['total']}
        return jsonify(query_result)

    if 'error' in query_result:
        ctx = {
            'q': query_params['q'],
            'error': query_result['error'],
            'results': [],
            'filters': {}
        }
    else:
        total_pages = calculate_total_pages(query_result, query_params['size'])

        if query_params['current_page'] > total_pages:
            query_params['current_page'] = total_pages

        facets = filter_facets(query_result['facets'], query_result['total'])
        facets = sort_facets(facets)

        year_facet = process_year_facet(request, facets)

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
            'error': None
        }

        if query_params['min_date'] is not sys.maxsize:
            ctx['min_year'] = query_params['min_date']
            ctx['max_year'] = query_params['max_date']

    ctx['modify_query'] = modify_query

    return render_template('hepdata_search/search_results.html', ctx=ctx)


@blueprint.route('/ids', methods=['GET'])
def all_ids():
    """
    Get IDs for all records (since a given date) as a JSON list of integers.

    Accepts query parameters:

    - ``inspire_ids``: if set to a truthy value, return inspire IDs rather than HEPData record IDs
    - ``last_updated``: return IDs updated since given date (in format YYYY-mm-dd)
    - ``sort_by``: if set to ``latest``, sort the results latest first
    - ``use_es``: if set to a truthy values, use OpenSearch rather than the database to return the ids
    """
    id_field = 'recid'
    if _get_bool_parameter(request, 'inspire_ids'):
        id_field = 'inspire_id'

    sort_latest_first = request.args.get('sort_by') == 'latest'

    last_updated = None
    last_updated_str = request.args.get('last_updated')
    if last_updated_str:
        try:
            last_updated = datetime.datetime.strptime(last_updated_str,
                                                      '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "error": "Unable to parse date from last_updated value %s. "
                         "last_updated should be in format YYYY-mm-dd"
                         % last_updated_str
            }), 400

    try:
        if _get_bool_parameter(request, 'use_es'):
            ids = es_get_all_ids(id_field=id_field, last_updated=last_updated, latest_first=sort_latest_first)
        else:
            ids = db_get_all_ids(id_field=id_field, last_updated=last_updated, latest_first=sort_latest_first)
    except ValueError as e:
        return jsonify({
            "error": "Error getting ids: %s" % e
        }), 400

    return jsonify([x for x in ids])


def _get_bool_parameter(request, name):
    string_value = request.args.get(name, '').lower()
    return string_value and string_value.lower() not in ['false', 'f']
