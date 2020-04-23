#
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


from __future__ import division
from datetime import date

MAX_AUTHOR_FACETS = 10
MAX_COLLABORATION_FACETS = 5
MAX_DATE_FACETS = 5
MAX_OTHER_FACETS = 5


def parse_aggregations(aggregations, query_filters=None):
    facets = []
    for agg_name, agg_res in aggregations.items():
        if agg_name == 'nested_authors' and 'author_full_names' in agg_res:
            buckets = agg_res['author_full_names']['buckets']
            facets.append(parse_author_aggregations(buckets))
        elif agg_name == 'collaboration':
            buckets = agg_res['buckets']
            facets.append(parse_collaboration_aggregations(buckets))
        elif agg_name == 'dates':
            buckets = agg_res['buckets']
            facets.append(parse_date_aggregations(buckets))
        elif agg_name == 'cmenergies':
            buckets = agg_res['buckets']
            facets.append(parse_cmenergies_aggregations(buckets, query_filters))
        else:
            buckets = agg_res.get('buckets')
            facets.append(parse_other_facets(buckets, agg_name))

    return [f for f in facets if f.get('vals')]


def parse_author_aggregations(buckets):
    for author_hit in buckets:
        author_hit['url_params'] = {'author': author_hit['key']}

    return {
        'type': 'author',
        'printable_name': 'Authors',
        'vals': buckets,
        'max_values': MAX_AUTHOR_FACETS
    }


def parse_collaboration_aggregations(buckets):
    for collab_hit in buckets:
        collab_hit['url_params'] = {'collaboration': collab_hit['key']}
        collab_hit['key'] = collab_hit['key'].upper()

    return {
        'type': 'collaboration',
        'printable_name': 'Collaboration',
        'vals': buckets,
        'max_values': MAX_COLLABORATION_FACETS
    }


def parse_cmenergies_aggregations(buckets, query_filters=None):
    max_limit = 100000
    min_limit = None
    valid_bucket_limits = None
    filtered_buckets = []

    if query_filters:
        cmenergy_filter_vals = [v for (k,v) in query_filters if k == 'cmenergies' and len(v) > 1]
        if cmenergy_filter_vals:
            min_limit = min([v[0] for v in cmenergy_filter_vals])
            max_limit = max([v[1] for v in cmenergy_filter_vals])
            valid_bucket_limits = [hit['key'] for hit in buckets if min_limit <= hit['key'] < max_limit]

    if not valid_bucket_limits:
        valid_bucket_limits = [hit['key'] for hit in buckets]

    for i in range(len(buckets)):
        cmenergy_hit = buckets[i]

        if cmenergy_hit['key'] in valid_bucket_limits:
            lower_limit = cmenergy_hit['key']

            if i+1 < len(buckets):
                upper_limit = buckets[i+1]['key']
            else:
                upper_limit = max_limit

            cmenergy_hit['url_params'] = {
                'cmenergies': "%.1f,%.1f" % (lower_limit, upper_limit)
            }

            # Unicode character reference:
            # \u221A is square root
            # \u2264 is <=
            # \u2265 is >=
            if upper_limit == 100000:
                cmenergy_hit['key'] = u"\u221As \u2265 %.1f" % lower_limit
            else:
                cmenergy_hit['key'] = u"%.1f \u2264 \u221As < %.1f" % (lower_limit, upper_limit)

            filtered_buckets.append(cmenergy_hit)

    return {
        'type': 'cmenergies',
        'printable_name': 'CM Energies (GeV)',
        'vals': filtered_buckets,
        'max_values': MAX_COLLABORATION_FACETS
    }


def parse_date_aggregations(buckets):
    for date_hit in buckets:
        timestamp = date.fromtimestamp(date_hit['key'] // 1000)
        date_hit['key'] = timestamp.year
        date_hit['url_params'] = {'date': date_hit['key']}

    buckets = sorted(buckets, key=lambda x: x['key'], reverse=True)
    buckets = sorted(buckets, key=lambda x: x['doc_count'], reverse=True)

    return {
        'type': 'date',
        'printable_name': 'Date',
        'vals': buckets,
        'max_values': MAX_DATE_FACETS
    }


def parse_other_facets(buckets, name):
    for hit in buckets:
        hit['url_params'] = {name: hit['key']}

    printable_name = name.capitalize()

    return {
        'type': name,
        'printable_name': printable_name,
        'vals': buckets,
        'max_values': MAX_OTHER_FACETS
    }
