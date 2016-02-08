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


class QueryBuilder(object):

    def __init__(self, query=None):
        if query:
            self.query = query
        else:
            self.query = {
                "query": {
                    "filtered": {
                        "query": {
                            "match_all": {}
                        }
                    }
                }
            }

    @staticmethod
    def generate_query_string(query_string='', fields=None):
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
    def generate_nested_query(path, query, fields):
        fields = [path + '.' + field for field in fields]
        return {
            "nested": {
                "path": path,
                "query": QueryBuilder.generate_query_string(query_string=query,
                                                            fields=fields)
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
        relation_dict = {
            relation: {
                "type": related_type,
                "query": related_query
            }
        }

        bool_operator = "must" if must else "should"
        query_dict = {
            "bool": {
                bool_operator: [relation_dict] + other_queries
            }
        }

        if "filtered" in self.query.get("query", {}):
            self.query["query"]["filtered"]["query"] = query_dict
        else:
            self.query.update({"query": query_dict})

    def add_query_string(self, query_string=''):
        query_dict = self.generate_query_string(query_string=query_string)

        if "filtered" in self.query.get("query", {}):
            self.query["query"]["filtered"]["query"] = query_dict
        else:
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
        from config.es_config import get_filter_clause
        filter_clauses = []
        for name, value in filters:
            clause = get_filter_clause(name, value)
            filter_clauses.append(clause)

        if filter_clauses and "filtered" in self.query.get("query", {}):
            self.query["query"]["filtered"]["filter"] = {"and": filter_clauses}

    def add_post_filter(self, postfilter):
        if postfilter is not None:
            self.query["post_filter"] = postfilter


def get_query_by_type(es_type, query_string=''):
    """ Get the query adjusted to the ES type
    (i.e. appropriate fields and boosting) """
    from config.es_config import default_queryable_fields
    fields = default_queryable_fields(es_type)
    return QueryBuilder.generate_query_string(query_string, fields)


def get_authors_query(query_string=''):
    """ Generate the nested query for authors (special case). """
    return QueryBuilder.generate_nested_query('authors',
                                              query_string,
                                              ['first_name', 'last_name'])
