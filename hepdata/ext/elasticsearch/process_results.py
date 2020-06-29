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


from .aggregations import parse_aggregations
from hepdata.config import CFG_DATA_TYPE, CFG_PUB_TYPE
from hepdata.utils.miscellaneous import splitter


def merge_results(pub_result, data_result):
    merge_dict = dict()
    merge_dict['hits'] = pub_result['hits']['hits'] + \
        data_result['hits']['hits']
    merge_dict['total'] = pub_result['hits']['total']['value']
    merge_dict['aggregations'] = pub_result.get('aggregations', {})
    return merge_dict


def map_result(es_result, query_filters=None):
    hits = es_result['hits']
    total_hits = es_result['total']
    aggregations = es_result['aggregations']

    # Separate
    tables, papers = splitter(hits, is_datatable)
    fetch_remaining_papers(tables, papers)
    aggregated = match_tables_to_papers(tables, papers)
    results = []
    for paper, datatables in aggregated:
        mapped_hit = get_basic_record_information(paper)
        data = list(map(get_basic_record_information, datatables))
        mapped_hit.update({
            'data': data,
            'total_tables': len(data),
        })
        results.append(mapped_hit)

    facets = parse_aggregations(aggregations, query_filters)

    return {'results': results,
            'facets': facets,
            'total': total_hits}


def match_tables_to_papers(tables, papers):
    aggregated = []
    for paper in papers:
        paper_id = int(paper['_id'])
        relevant_tables = [t for t in tables
                           if t['_source']['related_publication'] == paper_id]

        # Create a function to extract table numbers from their DOIs.
        def sort_key(elem):
            """ Get the table number from the DOI. """
            try:
                table_num = int(elem['_source']['doi'].split('/')[-1].lstrip('t'))
            except (ValueError, AttributeError):  # this shouldn't happen
                table_num = 0
            return table_num

        # Sort the tables into the order they appear in the record.
        relevant_tables.sort(key=sort_key)

        aggregated.append((paper, relevant_tables))

    return aggregated


def get_basic_record_information(record):
    from .utils import parse_and_format_date, tidy_bytestring
    source = record['_source']

    # Collaborations
    collaborations = source.get('collaborations', [])
    if isinstance(collaborations, str):
        collaborations = [collaborations]

    authors = source.get('summary_authors', None)
    if authors:
        authors = list(map(lambda x: x['full_name'], authors))

    datestring = source.get('creation_date')

    res = source
    res['collaborations'] = collaborations
    res['authors'] = authors
    res['date'] = parse_and_format_date(datestring)
    res['abstract'] = tidy_bytestring(source.get('abstract'))

    return res


def fetch_remaining_papers(tables, papers):
    from hepdata.ext.elasticsearch.api import fetch_record
    hit_papers = list(map(lambda x: int(x['_id']), papers))
    for table in tables:
        paper_id = table['_source'].get('related_publication')
        if paper_id and paper_id not in hit_papers:
            paper_source = fetch_record(paper_id, CFG_PUB_TYPE)
            paper = {'_id': str(paper_id), '_source': paper_source}
            papers.append(paper)
            hit_papers.append(paper_id)


def is_datatable(es_hit):
    return es_hit['_source']['doc_type'] == CFG_DATA_TYPE
