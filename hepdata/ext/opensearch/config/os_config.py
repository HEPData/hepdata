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
import math

from hepdata.config import CFG_DATA_KEYWORDS

# https://opensearch.org/docs/2.14/aggregations/bucket/terms/#size-and-shard-size-parameters
TERMS_SIZE = 20

def add_default_aggregations(search, filters=[]):
    """ Default aggregations used for computing facets """
    # Add authors field first, chaining to ensure it's nested
    search.aggs.bucket('nested_authors', 'nested', path='authors')\
        .bucket('author_full_names', 'terms', field='authors.full_name.raw', size=TERMS_SIZE)

    # Add remaining fields separately so they're added to the list
    search.aggs.bucket('collaboration', 'terms', field='collaborations.raw', size=TERMS_SIZE)
    search.aggs.bucket('subject_areas', 'terms', field='subject_area.raw', size=TERMS_SIZE)
    search.aggs.bucket('dates', 'date_histogram', field='publication_date', interval='year')
    search.aggs.bucket('reactions', 'terms', field='data_keywords.reactions.raw', size=TERMS_SIZE)
    search.aggs.bucket('observables', 'terms', field='data_keywords.observables.raw', size=TERMS_SIZE)
    search.aggs.bucket('phrases', 'terms', field='data_keywords.phrases.raw', size=TERMS_SIZE)

    # Don't add cmenergies aggregations for now as they're unsupported in ES 7.1
    # (added in ES 7.4)
    # Determine the interval for cmenergies buckets depending on the current filter
    # interval = 10
    # offset = 0
    # cmenergy_filters = [(k,v) for (k,v) in filters if k == 'cmenergies']
    # if cmenergy_filters:
    #     current_range = cmenergy_filters[0][1]
    #     offset = current_range[0]
    #     if len(current_range) == 2:
    #         span = current_range[1] - current_range[0]
    #         if span > 0 and span < 25:
    #             interval = math.ceil(span / 5)
    #         else:
    #             interval = 5
    #
    # search.aggs.bucket('cmenergies', 'histogram', field='data_keywords.cmenergies',
    #                    interval=interval, offset=offset, min_doc_count=10)

    return search


def get_filter_field(name, value):
    """ Returns an appropriate OS clause for a given filter """
    filter_type = "term"

    if name == 'collaboration':
        field = "collaborations.raw"

    elif name == 'subject_areas':
        field = "subject_area.raw"

    elif name == 'cmenergies':
        filter_type = "range"
        field = "data_keywords.cmenergies"

        # Ensure values are in the right order
        value.sort()

        val_dict = { "gte": value[0] }
        if len(value) > 1:
            key = "lt" if value[1] > value[0] else "lte"
            val_dict[key] = value[1]
        else:
            val_dict["lte"] = value[0]

        value = val_dict

    elif name == 'date':
        year_list = []
        for year in value:
            year_list.append(str(year))

        filter_type = "terms"
        value = year_list
        field = "year"

    elif name in CFG_DATA_KEYWORDS:
        field = "data_keywords." + name + ".raw"

    else:
        raise ValueError("Unknown filter: " + name)

    return (filter_type, field, value)


def sort_fields_mapping(sort_by):
    """ JSON mappings to OpenSearch fields used for sorting. """
    if sort_by == 'title':
        return 'title.raw'
    elif sort_by == 'collaborations':
        return 'collaborations.raw'
    elif sort_by == 'date':
        return 'creation_date'
    elif sort_by == 'latest':
        return 'last_updated'
    elif sort_by == 'recid':
        return 'recid'  # No change required
    elif sort_by == 'publication_recid':
        return 'publication_recid'  # No change required
    elif sort_by == 'inspire_id':
        return 'inspire_id'  # No change required
    elif not sort_by or sort_by == 'relevance':
        return '_score'
    else:
        raise ValueError('Sorting on field ' + sort_by + ' is not supported')


def default_sort_order_for_field(field):
    """ Determine the default sorting order (ascending vs descending)
    for each field type. """
    if field == 'title':
        return 'asc'
    elif field == 'collaborations':
        return 'asc'
    elif field == 'date':
        return 'desc'
    else:
        return 'desc'
