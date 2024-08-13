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
from opensearch_dsl import Q


class QueryBuilder:

    @staticmethod
    def add_filters(search, filters):
        from .config.os_config import get_filter_field

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
                "observables": "data_keywords.observables",
                "cmenergies": "data_keywords.cmenergies",
                "phrases": "data_keywords.phrases",
                "reactions": "data_keywords.reactions",
                "analysis": "analyses.type",
                "resources": "resources.description"  # Add shorthand for resource description
            }
        }

        new_query_string = query_string

        for query_part in re.split("AND|OR", query_string):
            query_part = query_part.strip()
            if ':' in query_part:
                _key, _value = query_part.split(':', maxsplit=1)
                _key = mapping['keys'].get(_key, _key)
                _value = HEPDataQueryParser._quote_phrase(_value)
                new_query_string = new_query_string.replace(query_part, f"{_key}:{_value}")
            else:
                new_query_string = new_query_string.replace(
                    query_part, HEPDataQueryParser()._quote_phrase(query_part)
                )

        return new_query_string

    @staticmethod
    def _quote_phrase(phrase):
        # Match phrases containing a reaction (including "-->") or a doi (word
        # chars with / in the middle) and quote them
        pattern = re.compile("(.*-->.*|[\w\.]+\/[\w\.]+)")

        if '"' not in phrase and pattern.fullmatch(phrase):
            return f'"{phrase}"'
        return phrase
