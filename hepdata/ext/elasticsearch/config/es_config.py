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

from hepdata.config import CFG_DATA_KEYWORDS


def add_default_aggregations(search):
    """ Default aggregations used for computing facets """
    # Add authors field first, chaining to ensure it's nested
    search.aggs.bucket('nested_authors', 'nested', path='authors')\
        .bucket('author_full_names', 'terms', field='authors.full_name.raw')

    # Add remaining fields separately so they're added to the list
    search.aggs.bucket('collaboration', 'terms', field='collaborations.raw')
    search.aggs.bucket('subject_areas', 'terms', field='subject_area.raw')
    search.aggs.bucket('dates', 'date_histogram', field='publication_date', interval='year')
    search.aggs.bucket('reactions', 'terms', field='data_keywords.reactions.raw')
    search.aggs.bucket('observables', 'terms', field='data_keywords.observables.raw')
    search.aggs.bucket('phrases', 'terms', field='data_keywords.phrases.raw')
    search.aggs.bucket('cmenergies', 'terms', field='data_keywords.cmenergies.raw')

    return search


def get_filter_field(name, value):
    """ Returns an appropriate ES clause for a given filter """
    filter_type = "term"

    if name == 'collaboration':
        field = "collaborations.raw"

    elif name == 'subject_areas':
        field = "subject_area.raw"

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
    """ JSON mappings to ElasticSearch fields used for sorting. """
    if sort_by == 'title':
        return 'title.raw'
    elif sort_by == 'collaborations':
        return 'collaborations.raw'
    elif sort_by == 'date':
        return 'creation_date'
    elif sort_by == 'latest':
        return 'last_updated'
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
