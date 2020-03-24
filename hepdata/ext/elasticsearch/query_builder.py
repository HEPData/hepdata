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

import re


class QueryBuilder(object):
    def __init__(self):
        self.query = {
            "query": {
                "bool": {
                    "must": {
                        "match_all": {}
                    }
                }
            }
        }

    @staticmethod
    def generate_query_string(query_string=''):
        if query_string:
            return {
                "query_string": {
                    "query": query_string,
                    "fuzziness": "AUTO"
                }
            }
        else:
            return {"match_all": {}}

    @staticmethod
    def generate_nested_query(path, query):
        return {
            "nested": {
                "path": path,
                "query": QueryBuilder.generate_query_string(query_string=query)
            }
        }

    def add_sorting(self, sort_field='', sort_order=''):
        from utils import calculate_sort_order
        from config.es_config import sort_fields_mapping

        mapped_sort_field = sort_fields_mapping(sort_field)
        self.query.update(dict(sort=[{
            mapped_sort_field: {
                "order": calculate_sort_order(sort_order, sort_field)
            }
        }]))

    def add_source_filter(self, includes, excludes):
        self.query.update({
            "_source": {"includes": includes, "excludes": excludes}
        })

    def add_pagination(self, size, offset=0):
        self.query.update({
            "size": size,
            "from": offset
        })

    def add_child_parent_relation(self,
                                  related_type,
                                  relation="child",
                                  related_query=None,
                                  must=False,
                                  other_queries=None):
        other_queries = [] if not other_queries else other_queries
        related_query = {} if not related_query else related_query

        relation = "has_child" if relation == "child" else "has_parent"
        type_key = "type" if relation == "child" else "parent_type"
        relation_dict = {
            relation: {
                type_key: related_type,
                "query": related_query
            }
        }

        bool_operator = "must" if must else "should"
        query_dict = {
            "bool": {
                bool_operator: [relation_dict] + other_queries
            }
        }

        self.query.update({"query": query_dict})


    def add_aggregations(self, aggs=None):
        from config.es_config import default_aggregations
        if not aggs:
            aggs = default_aggregations()

        self.query.update({"aggs": aggs})

    def add_highlighting(self, fields):
        self.query.update({
            "highlight": {
                "fields": {
                    field: {} for field in fields
                    }
            }
        })

    def add_filters(self, filters):
        from config.es_config import get_filter_clause, get_nested_clause
        filter_clauses = []
        nested_clause = None

        for name, value in filters:
            if name == "author":
                nested_clause = get_nested_clause(name, value)
            else:
                clause = get_filter_clause(name, value)
                filter_clauses.append(clause)

        if filter_clauses:
            self.query["query"]["bool"]["filter"] = filter_clauses

        if nested_clause:
            self.query["query"].pop("bool")
            self.query["query"]["nested"] = nested_clause

    def add_post_filter(self, postfilter):
        if postfilter is not None:
            self.query["post_filter"] = postfilter


class HEPDataQueryParser(object):
    @staticmethod
    def parse_query(query_string):
        # query should be something like 'observable:ASYM' which
        # would translate to data_keywords.observables:ASYM
        mapping = {
            "keys": {
                "observables": "data_keywords.observables:{0}",
                "cmenergies": "data_keywords.cmenergies:{0}",
                "phrases": "data_keywords.phrases:{0}",
                "reactions": "data_keywords.reactions:{0}"
            }
        }

        new_query_string = query_string

        for query_part in re.split("AND|OR", query_string):
            query_part = query_part.strip()
            if ':' in query_part:
                try:
                    _key_value = query_part.split(':')
                    _key = mapping['keys'][_key_value[0]].format(_key_value[1])
                    new_query_string = new_query_string.replace(query_part, "{0}".format(_key))
                except KeyError:
                    continue

        return new_query_string
