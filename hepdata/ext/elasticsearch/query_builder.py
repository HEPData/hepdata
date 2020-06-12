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
from elasticsearch_dsl import Q


class QueryBuilder:

    @staticmethod
    def add_filters(search, filters):
        from .config.es_config import get_filter_field

        for name, value in filters:
            if name == "author":
                search = search.query('nested', path='authors', query=Q('match', authors__full_name = value))
            else:
                (filter_type, field, value) = get_filter_field(name, value)
                search = search.filter(filter_type, **{field: value})

        return search


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
