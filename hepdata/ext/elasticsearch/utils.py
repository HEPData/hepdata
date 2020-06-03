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

from collections import defaultdict
from functools import reduce

from flask import current_app


def parse_and_format_date(datestring):
    """ Parse a date string into a nice readable format. """
    if not datestring:
        return None
    import dateutil.parser
    timedate = dateutil.parser.parse(datestring)
    return timedate.strftime('%d %b %Y')


def flip_sort_order(order):
    """ Flip the sort order from descending to ascending or vice-versa. """
    if order == 'asc':
        return 'desc'
    else:
        return 'asc'


def prepare_author_for_indexing(document):
    """ Extract the author list from the document and index it in a separate
     index. """

    index = current_app.config['AUTHOR_INDEX']

    author_data = []
    authors = document.get('authors', None)

    if authors is not None:
        for author in authors:
            data_dict = author

            op_dict = {
                "index": {
                    "_index": index,
                    "_id": author['full_name']
                }
            }
            author_data.append(op_dict)
            author_data.append(data_dict)

    return author_data


def calculate_sort_order(is_reversed, sorting_field):
    """ Take the default sort order for a given field and an information
     whether to flip it and compute the final sorting order. """
    from .config.es_config import default_sort_order_for_field
    default_sort_order = default_sort_order_for_field(sorting_field)
    if is_reversed == 'rev':
        return flip_sort_order(default_sort_order)
    else:
        return default_sort_order


def push_keywords(docs):
    """
        Add keywords from datatables to the corresponding publication record
    """
    from hepdata.utils.miscellaneous import splitter
    datatables, publications = splitter(docs,
                                        lambda d: 'related_publication' in d)
    if len(publications) == 0 and len(datatables) == 0:
        raise ValueError("Documents provided are not appropriate " +
                         "for pushing keywords")

    # check the related publication field

    for pub in publications:
        data = filter(lambda table:
                      table['related_publication'] == pub['recid'],
                      datatables)

        keywords = reduce(lambda acc, d: acc + d['keywords'], data, [])

        agg_keywords = defaultdict(list)
        for kw in keywords:
            agg_keywords[kw['name']].append(kw['value'])

        # Remove duplicates
        for k, v in agg_keywords.items():
            agg_keywords[k] = list(set(v))

        pub['data_keywords'] = agg_keywords

    return publications + datatables


def tidy_bytestring(bytestring):
    # Converts a python3-style bytestring literal e.g. "b'hello world'" into a normal string
    # We should be able to remove this method when we migrate to python3 and have reindexed
    if bytestring and bytestring.startswith("b'"):
        bytestring = bytestring.strip("b'\\n").strip()
    return bytestring
