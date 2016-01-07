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

from hepdata.config import CFG_DATA_KEYWORDS


def default_aggregations():
    """ Default aggregations used for computing facets """
    return {
        "nested_authors": {
            "nested": {
                "path": "authors",
            },
            "aggs": {
                "author_full_names": {
                    "terms": {
                        "field": "authors.full_name",
                    }
                }
            }
        },
        "collaboration": {
            "terms": {
                "field": "collaborations.raw",
                "size": 0,
            }
        },
        "dates": {
            "date_histogram": {
                "field": "creation_date",
                "interval": "year",
            }
        },
        "reactions": {
            "terms": {
                "field": "data_keywords.reactions.raw",
                # "min_doc_count": 2,
                "size": 0,
            }
        },
        "observables": {
            "terms": {
                "field": "data_keywords.observables.raw",
                # "min_doc_count": 2,
                "size": 0,
            }
        },
        "cmenergies": {
            "terms": {
                "field": "data_keywords.cmenergies.raw",
                # "min_doc_count": 2,
                "size": 0,
            }
        }
    }


def get_filter_clause(name, value):
    """ Returns an appropriate ES clause for a given filter """
    if name == 'author':
        clause = {
            "nested": {
                "path": "authors",
                "filter": {
                    "bool": {
                        "must": {
                            "term": {"authors.full_name": value}
                        }
                    }
                }
            }
        }
    elif name == 'collaboration':
        clause = {
            "bool": {
                "must": {
                    "term": {"collaborations.raw": value}
                }
            }
        }
    elif name == 'date':
        clause = {
            "range": {
                "creation_date": {
                    "gte": str(value),
                    "lte": str(value + 1)
                }
            }
        }
    elif name in CFG_DATA_KEYWORDS:
        clause = {
            "bool": {
                "must": {
                    "term": {"data_keywords." + name + ".raw": value}
                }
            }
        }
    else:
        raise ValueError("Unknown filter: " + name)

    return clause


def default_queryable_fields(es_type):
    """ Defines what JSON fields should be queried in a full text search for
    a given type. """
    if es_type == 'datatable':
        return ["title^3", "abstract.summary^10", "doi", "inspire_id"]
    elif es_type == 'publication':
        return ["title^10", "abstract.summary^6", "keywords.name^4",
                "keywords.value^6", "doi", "inspire_id",
                "data_keywords.observables^4", "data_keywords.cmenergies^4",
                "data_keywords.reactions^4"]
    else:
        raise ValueError(es_type + ' is not a valid ElasticSearch type')


def sort_fields_mapping(sort_by):
    """ JSON mappings to ElasticSearch fields used for sorting. """
    if sort_by == 'title':
        return 'title.raw'
    elif sort_by == 'collaborations':
        return 'collaborations'
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
