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
import unittest

from opensearchpy.exceptions import NotFoundError
from opensearch_dsl import Search, Index
from datetime import datetime
import pytest
from invenio_db import db
from unittest.mock import call

from hepdata.ext.opensearch.config.os_config import \
    add_default_aggregations, sort_fields_mapping
from hepdata.ext.opensearch import api as os_api
from hepdata.ext.opensearch.config.os_config import get_filter_field
from hepdata.ext.opensearch.document_enhancers import add_data_keywords, process_cmenergies
from hepdata.utils.miscellaneous import get_resource_data
from hepdata.ext.opensearch.process_results import merge_results, match_tables_to_papers, \
    get_basic_record_information, is_datatable
from hepdata.ext.opensearch.query_builder import QueryBuilder, HEPDataQueryParser
from hepdata.ext.opensearch.utils import flip_sort_order, parse_and_format_date, prepare_author_for_indexing, \
    calculate_sort_order, push_keywords
from hepdata.modules.records.importer.api import import_records
from hepdata.modules.submission.models import HEPSubmission, DataSubmission, DataResource
from invenio_search import current_search_client as os

from hepdata.modules.search.config import LIMIT_MAX_RESULTS_PER_PAGE, \
    HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE
from hepdata.modules.search.views import check_max_results
from hepdata.ext.opensearch.config.os_config import TERMS_SIZE

def test_query_builder_add_aggregations():
    s = Search()
    s = add_default_aggregations(s)
    assert(s.to_dict() == {
        "aggs": {
            # "cmenergies": {"histogram": {"field": "data_keywords.cmenergies", "interval": 10, "offset": 0, "min_doc_count": 10}},
            "collaboration": {"terms": {"field": "collaborations.raw", "size": TERMS_SIZE}},
            "dates": {"date_histogram": {"field": "publication_date",  "interval": "year"}},
            "nested_authors": {"aggs": {
                "author_full_names": {"terms": {"field": "authors.full_name.raw", "size": TERMS_SIZE}}},
                "nested": {"path": "authors"}
            },
            "observables": {"terms": {"field": "data_keywords.observables.raw", "size": TERMS_SIZE}},
            "phrases": {"terms": {"field": "data_keywords.phrases.raw", "size": TERMS_SIZE}},
            "reactions": {"terms": {"field": "data_keywords.reactions.raw", "size": TERMS_SIZE}},
            "subject_areas": {"terms": {"field": "subject_area.raw", "size": TERMS_SIZE}}
        }
    })

    # Test out different CM Energies filters
    # Uncomment these tests once we reinstate the cmenergies aggregations with ES>=7.4
    # s = add_default_aggregations(s, [('cmenergies', [5.0, 25.0])])
    # assert(s.to_dict()["aggs"]["cmenergies"] == {
    #     "histogram": {"field": "data_keywords.cmenergies", "interval": 4, "offset": 5, "min_doc_count": 10}
    # })
    # s = add_default_aggregations(s, [('cmenergies', [4.0, 8.0])])
    # assert(s.to_dict()["aggs"]["cmenergies"] == {
    #     "histogram": {"field": "data_keywords.cmenergies", "interval": 1, "offset": 4, "min_doc_count": 10}
    # })


def test_query_builder_add_filters():
    s = Search()
    s = QueryBuilder.add_filters(s, [
        ("author", "test_author"),
        ("collaboration", "test_collaboration"),
        ("subject_areas", "test_subject_area"),
        ("date", [2000, 2001, 2002]),
        ("reactions", "test_reaction"),
        ("cmenergies", [1000.0])
    ])

    assert(s.to_dict() == {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"collaborations.raw": "test_collaboration"}},
                    {"term": {"subject_area.raw": "test_subject_area"}},
                    {"terms": {"year": ["2000", "2001", "2002"]}},
                    {"term": {"data_keywords.reactions.raw": "test_reaction"}},
                    {"range": {
                        "data_keywords.cmenergies": {
                            'gte': 1000.0,
                            'lte': 1000.0
                        }
                    }}
                ],
                'must': [{
                    "nested": {
                        "path": "authors",
                        "query": {
                            "match": {
                                "authors.full_name": "test_author"
                            }
                        }
                    }
                }]
            }
        }
    })

    with pytest.raises(ValueError, match=r"Unknown filter: not_a_filter"):
        s = QueryBuilder.add_filters(s, [
            ("not_a_filter", "test_invalid_filter")
        ])


def test_get_filter_field_cmenergies():
    assert(get_filter_field('cmenergies', [1.0, 2.0])
           == ("range", "data_keywords.cmenergies", {'gte': 1.0, 'lt': 2.0}))
    assert(get_filter_field('cmenergies', [1.0])
           == ("range", "data_keywords.cmenergies", {'gte': 1.0, 'lte': 1.0}))
    assert(get_filter_field('cmenergies', [2.0, 1.0])
           == ("range", "data_keywords.cmenergies", {'gte': 1.0, 'lt': 2.0}))


def test_sort_fields_mapping():
    assert(sort_fields_mapping('title') == 'title.raw')
    assert(sort_fields_mapping('collaborations') == 'collaborations.raw')
    assert(sort_fields_mapping('date') == 'creation_date')
    assert(sort_fields_mapping('latest') == 'last_updated')
    assert(sort_fields_mapping(None) == '_score')

    with pytest.raises(ValueError, match=r'Sorting on field invalid_field is not supported'):
        sort_fields_mapping('invalid_field')


def test_query_parser():
    _test_query = "observables:ASYM"
    parsed_query_string = HEPDataQueryParser.parse_query(_test_query)
    assert (parsed_query_string == "data_keywords.observables:ASYM")

    _test_query2 = "observables:ASYM AND phrases:Elastic Scattering OR cmenergies:1.34"
    parsed_query_string2 = HEPDataQueryParser.parse_query(_test_query2)

    assert (parsed_query_string2 == "data_keywords.observables:ASYM "
                                    "AND data_keywords.phrases:Elastic Scattering "
                                    "OR data_keywords.cmenergies:1.34")

    _test_query3 = "observables:ASYM AND unknown_field:hello"
    parsed_query_string3 = HEPDataQueryParser.parse_query(_test_query3)

    assert (parsed_query_string3 == "data_keywords.observables:ASYM "
                                    "AND unknown_field:hello")

    _test_query4 = 'reactions:P P --> LQ LQ X AND doi:10.1007/s100520000432'
    parsed_query_string4 = HEPDataQueryParser.parse_query(_test_query4)

    assert (parsed_query_string4 == 'data_keywords.reactions:"P P --> LQ LQ X"'
                                    ' AND doi:"10.1007/s100520000432"')

    _test_query5 = 'P P --> LQ LQ X'
    parsed_query_string5 = HEPDataQueryParser.parse_query(_test_query5)

    assert (parsed_query_string5 == '"P P --> LQ LQ X"')

    _test_query6 = 'analysis:rivet'
    parsed_query_string6 = HEPDataQueryParser.parse_query(_test_query6)

    assert (parsed_query_string6 == 'analyses.type:rivet')

    _test_query7 = 'publication_recid:1'
    parsed_query_string7 = HEPDataQueryParser.parse_query(_test_query7)
    assert (parsed_query_string7 == 'recid:1')

def test_verify_range_query_term():
    """
    Tests the range query verification function to ensure that parsed queries are
    correctly returning the range term list, and the data search table exclusion status.
    """
    test_data =[
        {  # Expected to return publication_recid as it is default.
            "expected_result": ["recid"],
            "exclude_tables": False, # Recid should include tables in search
            "query_strings": [
                "recid:[0 TO 10000]", # Correct
                "recid: [0  TO  10000]",  # Extra valid whitespace
                " recid:[0 TO 10000] ",  # Left and right whitespace
                "recid:[0 TO 10000] AND year:2024"
            ]
        },
        {  # Expected to return publication_recid as it is default.
            "expected_result": ["publication_recid"],
            "exclude_tables": True, # publication_recid should exclude tables
            "query_strings": [
                "publication_recid:[0 TO 10000]",
                "publication_recid: [0  TO  10000]",  # Extra valid whitespace
                " publication_recid:[0 TO 10000] ",  # Left and right whitespace
                "publication_recid:[0 TO 10000] AND year:2024"
            ]
        },
        { # Test proper exclusion value of publication_recid and inspire_id
            "expected_result": ["publication_recid", "inspire_id"],
            "exclude_tables": True,
            "query_strings": [
                "publication_recid:[0 TO 10000] AND inspire_id:[0 TO 10000]",  # Correct
                "publication_recid: [0  TO  10000] AND inspire_id: [0  TO  10000]",  # Extra valid whitespace
                " publication_recid:[0 TO 10000] AND  inspire_id: [0  TO  10000]",  # Left and right whitespace
            ]
        },
        {
            "expected_result": ["recid", "inspire_id"],
            "exclude_tables": False,
            "query_strings": [
                "recid:[0 TO 10000] AND inspire_id:[0 TO 10000]",
                "recid: [0  TO  10000] AND inspire_id: [0  TO  10000]",  # Extra valid whitespace
                " recid:[0 TO 10000] AND  inspire_id: [0  TO  10000]",  # Left and right whitespace
            ]
        },
        {
            "expected_result": ["recid", "publication_recid"],
            "exclude_tables": False,
            "query_strings": [
                "recid:[0 TO 10000] AND publication_recid:[0 TO 10000]",
                "recid: [0  TO  10000] AND publication_recid: [0  TO  10000]",  # Extra valid whitespace
                " recid:[0 TO 10000] AND  publication_recid: [0  TO  10000]",  # Left and right whitespace
            ]
        },
        {  # Some incorrect cases
            "expected_result": [],
            "exclude_tables": False,
            "query_strings": [
                " recid[0 TO 10000] ",
                "recsid:[0 TO 10000]",
                "INCORRECT:[46 TO 46]",  # Mismatched term
                "recid:[-0 TO 10000] OR inspire_id:[-123 TO -123]", # Negative numbers
                "recid:[NOTINT TO 46]",  # Mismatched int left
                "recid:[46 TO NOTINT]",  # Mismatched int right
                "inspire_idd:[0 TO 10000]",  # Misspelling
                "inspire_id:[0 TO 10000 ]",  # Invalid whitespace
                "inspire_id:[ 0 TO 10000]",  # Invalid whitespace
                "inspire_id :[0 TO 10000]",  # Invalid whitespace
            ]
        },

    ]

    # Each test dictionary in the list has a different expected_result value
    for test in test_data:
        # For each query string for the current expected_result
        for query in test["query_strings"]:
            # Execute the verification with current string
            result = HEPDataQueryParser.parse_range_query(query)
            # Expected result based on which test object we are on
            assert result == (test["expected_result"], test["exclude_tables"])


def test_search(app, load_default_data, identifiers):
    """
    Test the search functions work correctly, also with the new query syntax.
    Testing both standard and authors search here to save loading the data multiple times
    :return:
    """
    index = app.config.get('OPENSEARCH_INDEX')

    # Test searching with an empty query
    results = os_api.search('', index=index)
    assert(results['total'] == len(identifiers))
    assert(len(results['facets']) == 8)
    assert(len(results['results']) == len(identifiers))

    for i in identifiers:
        assert i['title'] in [r['title'] for r in results['results']]
        assert i['inspire_id'] in [r['inspire_id'] for r in results['results']]
        table_result = next((r['data'] for r in results['results'] if r['inspire_id'] == i['inspire_id']))
        assert i['data_tables'] == len(table_result)

    # Test pagination (1 item per page as we only have 2; get 2nd page)
    results = os_api.search('', index=index, size=1, offset=1)
    assert(results['total'] == len(identifiers))
    assert(len(results['results']) == 1)
    assert(results['results'][0]['title'] in [i['title'] for i in identifiers])

    # Test a simple search query from the second test submission
    # The search matches the publication but not the data tables
    results = os_api.search('charmonium', index=index)
    assert(results['total'] == 1)
    assert(results['results'][0]['inspire_id'] == identifiers[1]['inspire_id'])
    assert(len(results['results'][0]['data']) == 0)

    # Test a complex querystring that maps across main doc and nested authors field
    results = os_api.search("title:asymmetry AND authors.full_name:Orbaker", index=index)
    assert(results['total'] == 1)
    assert(results['results'][0]['inspire_id'] == identifiers[0]['inspire_id'])

    # Test the authors search (fuzzy)
    results = os_api.search_authors('Bal')
    expected = [
        {'full_name': 'Pal, Arnab', 'affiliation': 'Texas U., Arlington'},
        {'full_name': 'Bala, A.', 'affiliation': 'Panjab U.'},
        {'full_name': 'Balz, Johannes', 'affiliation': 'Mainz U.'},
        {'full_name': 'Evans, Hal', 'affiliation': 'Indiana U.'},
        {'full_name': "O'Shea, Val", 'affiliation': 'Glasgow U.'},
        {'full_name': 'Dal Santo, Daniele', 'affiliation': 'Bern U., LHEP'},
        {'full_name': 'Garg, Rocky Bala', 'affiliation': 'SLAC'},
        {'full_name': 'Tal Hod, Noam', 'affiliation': 'Weizmann Inst.'},
        {'full_name': 'Arbiol Val, Sergio Javier', 'affiliation': 'Cracow, INP'},
        {'full_name': 'Van Daalen, Tal Roelof', 'affiliation': 'Washington U., Seattle'},
        {'full_name': 'Al Khoury, Konie', 'affiliation': 'Nevis Labs, Columbia U.'}
    ]

    assert(len(results) == len(expected))
    for author in expected:
        assert(author in results)

    # Test searching of data resource descriptions
    resource_text = 'Created with hepdata_lib 0.11.0' # Some text from a resource
    # Test alias for the resource searching
    resource_aliases = ['resources', 'resources.description']
    for alias in resource_aliases:
        search_query = f'{alias}:"{resource_text}"'
        results = os_api.search(search_query, index=index)
        # Check for the text within the resource results
        assert resource_text in results['results'][0]['resources'][0]['description']

    # Test searching of the resources field by type.
    # A bunch of different types to be checked for
    resource_types = ['png', 'html', 'zenodo', 'dat', 'C++', None]
    for res_type in resource_types:
        # Execute search for the current type
        results = os_api.search(f'resources.type:{res_type}', index=index)

        if res_type:
            result_resources = results['results'][0]['resources']
            # Compile all resource types for the first result
            result_data = [res['type'] for res in result_resources]
            assert res_type in result_data
        else:
            # Confirming that a blank entry (None) does not yield results
            assert len(results['results']) == 0

    # Search query string for the url search
    url_texts = ["https://zenodo.org/", None]

    for url_text in url_texts:
        # Execute the url search
        results = os_api.search(f'resources.url:"{url_text}"', index=index)

        if url_text:
            # Generate the urls from the result submission
            result_data = [res['url'] for res in results['results'][0]['resources']]
            # Confirm that at least one of the resources in result matches
            assert any(url.startswith(url_text) for url in result_data)
        else:
            # Confirming that a blank entry (None) does not yield results
            assert len(results['results']) == 0

    # Abstract text searching
    abstracts = ['This paper presents a search for pair production of higgsinos', None]
    for abstract_text in abstracts:
        # Execute the data_abstract search
        results = os_api.search(f'data_abstract:{abstract_text}', index=index)

        # If it is not a None
        if abstract_text:
            assert abstract_text in results['results'][0]['abstract']
        else:
            # Confirming that a blank entry (None) does not yield results
            assert len(results['results']) == 0

    # Test searching for a table using very specific text
    # Some description text from the test data
    description_text = 'Observed ASYMFB(LEPTON) as a function of PT(LEPTON) at reconstruction level.'
    results = os_api.search(description_text, index=index)

    # Create the table doi. We are expecting the first table to contain this data
    result_doi = results['results'][0]["hepdata_doi"] + ".v1/t1"

    # Load DataSubmission object to verify description vs query
    verify_submission = DataSubmission.query.filter_by(doi=result_doi).first()
    assert description_text in verify_submission.description

    # Test search queries that OS can't parse
    results = os_api.search('/', index=index)
    assert results == {'error': 'Failed to parse query [/]'}

    results = os_api.search('cmenergies:[1.3%20TO%201.4]', index=index)
    assert results == {'error': 'Failed to parse query [data_keywords.cmenergies:[1.3%20TO%201.4]]'}

    results = os_api.search('(SELECT (CHR(113)||CHR(122)||CHR(122)||CHR(122)||CHR(113))||(SELECT (CASE WHEN (6242=6242) THEN 1 ELSE 0 END))::text||(CHR(113)||CHR(120)||CHR(107)||CHR(98)||CHR(113)))', index=index)
    assert results == {'error': 'Failed to parse query [(SELECT (CHR(113)||CHR(122)||CHR(122)||CHR(122)||CHR(113))||(SELECT (CASE WHEN (6242=6242) THEN 1 ELSE 0 END))::text||(CHR(113)||CHR(120)||CHR(107)||CHR(98)||CHR(113)))]'}

    # Test a search query to an invalid index
    results = os_api.search('hello', index='thisisnotanindex')
    assert results == {'error': 'An unexpected error occurred: index_not_found_exception'}


def test_search_range_ids(app, load_default_data, identifiers):
    """
    Tests range-based searching where ID-like entries are used
    First checks whole range, then single entry
    e.g. inspire_id and recid NOT cmenergies etc.
    """

    # Test the parsed entries in config.CFG_SEARCH_RANGE_TERMS
    test_queries = [
        "inspire_id",
        "recid"
    ]

    for test in test_queries:
        # Create the range query formatting the keyword per query
        range_query = f"{test}:[%d TO %d]"

        # Just do a huge range, to see if everything appears
        results = os_api.search(range_query % (0, 100000000))
        # Result count should equal maximum number of entries
        assert len(results['results']) == len(identifiers)

        # Testing a range query we know shouldn't work
        zero_result = os_api.search(range_query % (0, 0))
        assert not zero_result.get('results')

        # Do a range search for a single result, for each result of the 'all' search above.
        for result in results['results']:
            # We get the inspire/recid from the current result
            identifier_id = int(result[test])
            # Do a search, formatting the query to find a single result
            specific_result = os_api.search(range_query % (identifier_id, identifier_id))
            # Check ID of single result
            assert int(specific_result['results'][0][test]) == int(identifier_id)

            # Testing another bad result, where the numbers are completely invalid
            bad_result = os_api.search(range_query % (identifier_id+1, identifier_id-1))
            assert not bad_result.get('results')

def test_range_queries(app, load_default_data, identifiers):
    """
    Tests search functionality to ensure range queries are functional, together
     and alongside other search types
    """
    current_year = datetime.today().year

    test_data = [
        {  # Check all results are returned, and is sorted by inspire_id
            "test_query": "inspire_id:[0 TO 10000000]",
            "expected_result": {
                "count": len(identifiers),
                "expected_inspire_ids": [2751932, 1283842, 1245023],
                "expected_rec_ids": [57, 1, 16]
            }
        },
        {  # Check all results are returned, and is sorted by recid
            "test_query": "publication_recid:[0 TO 10000000]",
            "expected_result": {
                "count": len(identifiers),
                "expected_inspire_ids": [2751932, 1245023, 1283842],
                "expected_rec_ids": [57, 16, 1]
            }
        },
        {  # Should cover every ID in the range, and equal the length of identifiers, sorted by recid
            "test_query": "inspire_id:[0 TO 10000000] AND publication_recid:[0 TO 10000000]",
            "expected_result": {
                "count": len(identifiers),
                "expected_inspire_ids": [2751932, 1245023, 1283842],
                "expected_rec_ids": [57, 16, 1]
            }
        },
        {  # Valid search for a specific entry
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57]",
            "expected_result": {
                "count": 1,
                "expected_inspire_ids": [2751932],
                "expected_rec_ids": [57]
            }
        },
        {  # Valid search for a specific entry using OR
            "test_query": "inspire_id:[2751932 TO 2751932] OR publication_recid:[0 TO 0]",
            "expected_result": {
                "count": 1,
                "expected_inspire_ids": [2751932],
                "expected_rec_ids": [57]
            }
        },
        {  # Valid search for a specific entry using OR
            "test_query": "inspire_id:[0 TO 0] OR publication_recid:[57 TO 57]",
            "expected_result": {
                "count": 1,
                "expected_inspire_ids": [2751932],
                "expected_rec_ids": [57]
            }
        },
        {  # Testing adding year to the range
            "test_query": f"inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] AND year:{current_year}",
            "expected_result": {
                "count": 1,
                "expected_inspire_ids": [2751932],
                "expected_rec_ids": [57]
            }
        },
        {  # Should be invalid as all entries are set to current year
            "test_query": f"inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] AND year:{current_year - 1}",
            "expected_result": {
                "count": 0,
                "expected_inspire_ids": [],
                "expected_rec_ids": []
            }
        },
        {  # Search text is valid here
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] Production of higgsinos",
            "expected_result": {
                "count": 1, "expected_inspire_ids": [2751932], "expected_rec_ids": [57]
            }
        },
        {  # Search text is valid here
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] AND Production of higgsinos",
            "expected_result": {
                "count": 1, "expected_inspire_ids": [2751932], "expected_rec_ids": [57]
            }
        },
        {  # Search text is invalid as it has been garbled slightly
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] AND Prdction of igsnos",
            "expected_result": {
                "count": 0, "expected_inspire_ids": [], "expected_rec_ids": []
            }
        },
        {  # No result as the search string is invalid
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[57 TO 57] AND \"abcdef\"",
            "expected_result": {
                "count": 0, "expected_inspire_ids": [], "expected_rec_ids": []
            }
        },
        {  # No result expected as inspire_id should not be matched
            "test_query": "inspire_id:[2751933 TO 2751933] AND publication_recid:[57 TO 57]",
            "expected_result": {
                "count": 0, "expected_inspire_ids": [], "expected_rec_ids": []
            }
        },
        {  # Result expected as inner resource recid is searched matched
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[58 TO 58]",
            "expected_result": {
                "count": 1, "expected_inspire_ids": [2751932], "expected_rec_ids": [57]
            }
        },
        {  # No result as publication_recid is incorrect
            "test_query": "inspire_id:[2751932 TO 2751932] AND publication_recid:[5000 TO 5000]",
            "expected_result": {
                "count": 0, "expected_inspire_ids": [], "expected_rec_ids": []
            }
        }
    ]

    for test in test_data:
        # Execute the search
        results = os_api.search(test['test_query'])

        # Gather the recid and inspire_id results
        recid_results = [result['recid'] for result in results['results']]
        inspire_results = [int(result['inspire_id']) for result in results['results']]

        # Confirm expected count
        assert len(results['results']) == test['expected_result']['count']
        # Confirm recid and inspire_id results are as expected
        assert test['expected_result']["expected_inspire_ids"] == inspire_results
        assert test['expected_result']["expected_rec_ids"] == recid_results


def test_merge_results():
    pub_result = {
        "hits": {
            "hits": [{"key": "testa"}],
            "total": { "value": 2, "relation": "eq" }
        }
    }
    data_result = {
        "hits": {
            "hits": [{"key": "testb"}],
            "total": { "value": 1, "relation": "eq" }
        }
    }

    merged = merge_results(pub_result, data_result)
    assert ("hits" in merged)
    assert (len(merged["hits"]) == 2)
    assert (merged["total"] == 2)


def test_flip_sort_order():
    order = "desc"
    order = flip_sort_order(order=order)
    assert (order is "asc")
    order = flip_sort_order(order=order)
    assert (order is "desc")


def test_parse_date():
    date = parse_and_format_date("09-01-2016")
    assert (date == "01 Sep 2016")

    date = parse_and_format_date(None)
    assert (date is None)


def test_calculate_sort_order():
    sort_title = calculate_sort_order(None, "title")

    assert (sort_title is "asc")

    sort_title_rev = calculate_sort_order("rev", "title")
    assert (sort_title_rev is "desc")

    sort_collaborations = calculate_sort_order(None, "collaborations")
    assert (sort_collaborations is "asc")

    sort_date = calculate_sort_order(None, "date")
    assert (sort_date is "desc")

    sort_other = calculate_sort_order(None, "reactions")
    assert (sort_other is "desc")


def test_push_keywords():
    docs = [
        {"recid": 1, "authors": [], "title": "Test",
         "keywords": [""]},
        {"recid": 2, "related_publication": 1, "keywords": [{"name": "reaction", "value": "PP --> PP"}]},
        {"recid": 3, "related_publication": 1, "keywords": [{"name": "reaction", "value": "PP --> PX"}]},
    ]

    pushed_result = push_keywords(docs)

    for results in pushed_result:
        if results["recid"] == 1:
            assert (results["data_keywords"] is not None)
            assert ("reaction" in results["data_keywords"])
            assert (len(results["data_keywords"]["reaction"]) == 2)
            assert ("PP --> PP" in results["data_keywords"]["reaction"])
            assert ("PP --> PX" in results["data_keywords"]["reaction"])

    try:
        push_keywords([])
    except ValueError as ve:
        assert (ve)


def test_add_data_keywords():
    # Check that only valid keywords are added to data_keywords
    original_keywords = [
        {'name': 'reactions', 'value': 'PBAR P --> LEPTON JETS X', 'synonyms': ''},
        {'name': 'observables', 'value': 'ASYM', 'synonyms': ''},
        {'name': 'phrases', 'value': 'Inclusive', 'synonyms': ''},
        {'name': 'phrases', 'value': 'Asymmetry Measurement', 'synonyms': ''},
        {'name': 'phrases', 'value': 'Jet Production', 'synonyms': ''},
        {'name': 'cmenergies', 'value': '1960.0', 'synonyms': ''},
        {'name': 'NOTAREALKEYWORD', 'value': 'banana', 'synonyms': ''}
    ]
    doc = {
        'keywords': original_keywords
    }
    add_data_keywords(doc)
    assert doc['keywords'] == original_keywords
    assert 'data_keywords' in doc
    assert len(doc['data_keywords']) == 4
    assert doc['data_keywords']['reactions'] == ['PBAR P --> LEPTON JETS X']
    assert doc['data_keywords']['observables'] == ['ASYM']
    assert set(doc['data_keywords']['phrases']) == \
        set(['Asymmetry Measurement', 'Inclusive', 'Jet Production'])
    assert doc['data_keywords']['cmenergies'] == [{'gte': 1960.0, 'lte': 1960.0}]
    assert 'NOTAREALKEYWORD' not in doc['data_keywords']


def test_process_cmenergies():
    test_keywords = {
        "cmenergies": [
            "0.5",
            "13000",
            "2.441 - 2.683",
            "3.683-3.441",
            "1.2 - 2.6 GeV",
            "91.2 GeV",
            "2.0gev",
            "5020 and 2760",
            "5020 AND 7000",
            "2076.0+5020.0",
            "invalid cmenergy"
        ]
    }
    expected = {
        'cmenergies': [
            {'gte': 0.5, 'lte': 0.5},
            {'gte': 13000.0, 'lte': 13000.0},
            {'gte': 2.441, 'lte': 2.683},
            {'gte': 3.441, 'lte': 3.683},
            {'gte': 1.2, 'lte': 2.6},
            {'gte': 91.2, 'lte': 91.2},
            {'gte': 2.0, 'lte': 2.0},
            {'gte': 2760.0, 'lte': 5020.0},
            {'gte': 5020.0, 'lte': 7000.0},
            {'gte': 2076.0, 'lte': 5020.0}
        ]
    }

    results = process_cmenergies(test_keywords)
    assert(len(results['cmenergies']) == len(expected['cmenergies']))

    for cmenergy in expected['cmenergies']:
        assert(cmenergy in results['cmenergies'])


def test_prepare_authors_for_indexing(app):
    with app.app_context():
        test_document = {
            "authors": [
                {"full_name": "John"},
                {"full_name": "Michael"}
            ]
        }

        bulk_doc = prepare_author_for_indexing(test_document)

        assert (len(bulk_doc) == 4)


def test_match_tables_to_papers():
    papers = [
        {"_id": 1, "recid": 1, "authors": [], "title": "Test",
         "keywords": [""], "_source": {"version": 2}},

        {"_id": 4, "recid": 4, "authors": [], "title": "Test 2",
         "keywords": [""], "_source": {"version": 2}}

    ]

    tables = [
        {"recid": 2, "_source": {"related_publication": 1, "title": "Table1", "doi": "10.17182/hepdata.1234.v2/t1",
                                 "keywords": [{"name": "reaction", "value": "PP --> PP"}]}},
        {"recid": 3, "_source": {"related_publication": 1, "title": "Table2", "doi": "10.17182/hepdata.1234.v2/t2",
                                 "keywords": [{"name": "reaction", "value": "PP --> PX"}]}}
    ]

    aggregated = match_tables_to_papers(tables, papers)

    assert (aggregated is not [])
    assert (len(aggregated) == 2)

    tables[0]["_source"]["doi"] = "10.17182/hepdata.1234.v2/t1a"  # invalid DOI format
    aggregated = match_tables_to_papers(tables, papers)
    assert (len(aggregated) == 2)

    tables[0]["_source"]["doi"] = None  # missing DOI
    aggregated = match_tables_to_papers(tables, papers)
    assert (len(aggregated) == 2)


def test_get_basic_record_information():
    test_record = {
        "_source": {
            "summary_authors": [
                {"full_name": "Silvia Smith"},
                {"full_name": "Tom Jones"}
            ],
            "collaborations": "ATLAS",
            "creation_date": "09-01-2016"
        }
    }

    record_info = get_basic_record_information(test_record)

    assert (record_info["collaborations"][0] == "ATLAS")
    assert (len(record_info["authors"]) == 2)
    assert (record_info["date"] == "01 Sep 2016")


def test_is_datatable():
    assert (is_datatable({"_source": {"doc_type": "datatable"}}))
    assert (not is_datatable({"_source": {"doc_type": "publication"}}))


def test_reindex_all(app, load_default_data, identifiers, mocker):
    index = app.config.get('OPENSEARCH_INDEX')
    # Delete the default index
    os.indices.delete(index=index)

    # Check we can't search
    results = os_api.search('', index=index)
    assert results == {'error': 'An unexpected error occurred: index_not_found_exception'}

    # Reindex, recreating the index
    os_api.reindex_all(index=index, recreate=True, synchronous=True)

    # Search should work again
    results = os_api.search('', index=index)
    assert(results['total'] == len(identifiers))

    # Test indexing record with no data tables
    results = os_api.search('electroweak', index=index)
    assert(results['total'] == 0)
    # Import inspire id 1478981 which has no data tables
    import_records(['1478981'], synchronous=True)
    os_api.reindex_all(index=index, synchronous=True)
    results = os_api.search('electroweak', index=index)
    assert(results['total'] == 1)
    assert(results['results'][0]['data'] == [])

    # Reindex, requesting update of mapping
    os_api.reindex_all(index=index, recreate=False, update_mapping=True, synchronous=True)

    # Test other params using mocking
    m = mocker.patch('hepdata.ext.opensearch.api.reindex_batch')

    # Start and end at publication_recid 1, batch size 2:
    # should call reindex_batch twice with submission ids [1] then [2]
    os_api.reindex_all(index=index, start=1, batch=2, synchronous=True)
    m.assert_has_calls([
        call([1, 2], index),
        call([3, 4], index)
    ])
    m.reset_mock()

    # Start and end at publication_recid 1:
    # should call reindex_batch with submission ids [1]
    os_api.reindex_all(index=index, start=1, end=1, synchronous=True)
    m.assert_called_once_with([1], index)
    m.reset_mock()

    # Start at publication_recid 16, end at 100:
    # should call with submission ids [2, 3]
    os_api.reindex_all(index=index, start=16, end=100, synchronous=True)
    m.assert_called_once_with([2, 3, 4], index)
    m.reset_mock()

    # Start at publication_recid 16, end at 1, batch size 10:
    # should fix max/min order and call with submission ids [1, 2]
    os_api.reindex_all(index=index, start=16, end=1, batch=10, synchronous=True)
    m.assert_called_once_with([1, 2], index)
    m.reset_mock()

    # Create a new version for ins1478981
    new_submission = HEPSubmission(publication_recid=57, inspire_id='1478981', version=2, overall_status='todo')
    db.session.add(new_submission)
    db.session.commit()
    # New id should be 5
    assert(new_submission.id == 5)
    # Reindex should still index submission 3 and 4 as 5 is not finished
    os_api.reindex_all(index=index, synchronous=True)
    m.assert_called_once_with([1, 2, 3, 4], index)
    m.reset_mock()

    # Update submission to have status finished
    new_submission.overall_status='finished'
    db.session.add(new_submission)
    db.session.commit()
    # Reindex should now index 4 instead of 3
    os_api.reindex_all(index=index, synchronous=True)
    m.assert_called_once_with([1, 2, 4, 5], index)
    m.reset_mock()

    # Create a further new version for ins1478981
    new_submission2 = HEPSubmission(publication_recid=57, inspire_id='1478981', version=3, overall_status='todo')
    db.session.add(new_submission2)
    db.session.commit()
    # New id should be 6
    assert(new_submission2.id == 6)
    # Reindex should still index submission 4 as 6 is not finished
    os_api.reindex_all(index=index, synchronous=True)
    m.assert_called_once_with([1, 2, 4, 5], index)
    m.reset_mock()

    # Update submission to have status finished
    new_submission2.overall_status='finished'
    db.session.add(new_submission2)
    db.session.commit()
    # Reindex should now index 5 instead of 4
    os_api.reindex_all(index=index, synchronous=True)
    m.assert_called_once_with([1, 2, 4, 6], index)


def test_reindex_batch(app, load_default_data, mocker):
    index = app.config.get('OPENSEARCH_INDEX')

    # Mock methods called so we can check they're called with correct parameters
    mock_index_record_ids = mocker.patch('hepdata.ext.opensearch.api.index_record_ids')
    mock_push_data_keywords = mocker.patch('hepdata.ext.opensearch.api.push_data_keywords')

    # Reindex submission id 1 (pub_recid=1, with data submissions 2-15)
    mock_index_record_ids.return_value = {'publication': [1], 'datatable': list(range(2,16))}
    os_api.reindex_batch([1], index)
    mock_index_record_ids.assert_called_once_with(list(range(1, 16)), index=index)
    mock_push_data_keywords.assert_called_once_with(pub_ids=[1])
    mock_index_record_ids.reset_mock()
    mock_push_data_keywords.reset_mock()

    # Reindex submission id 2 (pub_recid=16, data submissions 17-56)
    mock_index_record_ids.return_value = {'publication': [16], 'datatable': list(range(17,56))}
    os_api.reindex_batch([2], index)
    mock_index_record_ids.assert_called_once_with(list(range(16, 57)), index=index)
    mock_push_data_keywords.assert_called_once_with(pub_ids=[16])


def test_update_record_mapping(app, mocker):
    index_name = 'mock_index'
    index = Index(using=os, name=index_name)
    index.delete(ignore=404)
    index.create()

    mapping = index.get_mapping()
    assert mapping == {'mock_index': {'mappings': {}}}

    # Update record mapping with the real one - should succeed as it's adding fields
    os_api.update_record_mapping(index=index_name)

    # mapping should be as defined in record_mapping
    mapping = index.get_mapping(using=os)
    from hepdata.ext.opensearch.config.record_mapping import mapping as real_mapping
    assert 'properties' in mapping['mock_index']['mappings']
    for k in real_mapping.keys():
        assert k in mapping['mock_index']['mappings']['properties']

    # Recreate index with a mapping that's incompatible with the real one
    index.delete(ignore=404)
    index.create()
    mapping = {
        "doc_type": {
            "type": "date"
        }
    }
    index.put_mapping(using=os, body={ "properties": mapping })

    # Update record mapping with the real one - should give exception
    with pytest.raises(ValueError) as excinfo:
        os_api.update_record_mapping(index=index_name)

    msg = str(excinfo.value)
    assert msg.startswith("Unable to update record mapping: mapper [doc_type]")
    assert msg.endswith("You may need to recreate the index to update the mapping.")


def test_get_record(app, load_default_data, identifiers):
    record = os_api.get_record(1)
    for key in ["inspire_id", "title"]:
        assert (record[key] == identifiers[0][key])

    assert(os_api.get_record(9999999) is None)


def test_get_all_ids(app, load_default_data, identifiers):
    expected_record_ids = [1, 16, 57]
    # Pre-sorted based on the last_updated (today, 2016-07-13 and 2013-12-17)
    sorted_expected_record_ids = [57, 1, 16]
    # Order is not guaranteed by OS unless we use latest_first,
    # so sort the results before checking
    assert(set(os_api.get_all_ids()) == set(expected_record_ids))

    # Check id_field works
    assert(os_api.get_all_ids(id_field='recid') == expected_record_ids)
    assert(os_api.get_all_ids(id_field='inspire_id')
           == [int(x["inspire_id"]) for x in identifiers])
    with pytest.raises(ValueError):
        os_api.get_all_ids(id_field='authors')

    # Check last_updated works
    # Default records were last updated on 2016-07-13 and 2013-12-17
    date_2013_1 = datetime(year=2013, month=12, day=16)
    assert(os_api.get_all_ids(last_updated=date_2013_1) == expected_record_ids)
    date_2013_2 = datetime(year=2013, month=12, day=17)
    assert(os_api.get_all_ids(last_updated=date_2013_2) == expected_record_ids)
    date_2013_3 = datetime(year=2013, month=12, day=18)
    assert(os_api.get_all_ids(last_updated=date_2013_3) == [1, 57])
    date_2120 = datetime(year=2120, month=1, day=1)
    assert(os_api.get_all_ids(last_updated=date_2120) == [])

    # Check sort by latest works - first record is newer than previous
    assert(os_api.get_all_ids(latest_first=True) == sorted_expected_record_ids)


@pytest.mark.parametrize("input_size, output_size",
    [
        (None, HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE),
        (0, HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE),
        (HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE, HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE),
        (LIMIT_MAX_RESULTS_PER_PAGE, LIMIT_MAX_RESULTS_PER_PAGE),
        (LIMIT_MAX_RESULTS_PER_PAGE + 1, LIMIT_MAX_RESULTS_PER_PAGE),
        ('all', HEPDATA_CFG_DEFAULT_RESULTS_PER_PAGE)
    ]
)
def test_check_max_results(input_size, output_size):
    args = {'size': input_size} if input_size is not None else {}
    check_max_results(args)
    assert args['size'] == output_size


def test_get_resource_data(app):
    """
        Tests the get_resource_data document_enhancers function.
        Ensures correct generation of resource dictionary from
            a given HEPSubmission object.
    """

    test_data = [
        # Each dictionary represents one HEPSubmission object
        # containing the resources
        {
            "resources": [
                DataResource(
                    file_description="Test",
                    file_type="html",
                    file_location="http://www.google.com/"
                ),
                DataResource(
                    id=1,
                    file_description="Test",
                    file_type="type",
                    file_location="Some kind of text"
                )
            ]
        },
        {  # Testing against a blank entry
            "resources": []
        }
    ]

    # Create test HEPSubmission object
    test_submission = HEPSubmission()
    for test in test_data:
        # Set the resources value upon each iteration
        test_submission.resources = test["resources"]

        # Run the test function to generate dictionary
        result = get_resource_data(test_submission)

        # Generate the expected results
        expected_results = []
        for test_res in test_submission.resources:
            expected = {
                "description": test_res.file_description,
                "type": test_res.file_type
            }

            # We only expect the original file_location to be returned
            # If it starts with http, otherwise generated URL is expected
            if test_res.file_location.startswith("http"):
                expected["url"] = test_res.file_location
            else:
                site_url = app.config.get('SITE_URL', 'https://www.hepdata.net')
                expected["url"] = f"{site_url}/record/resource/{test_res.id}?landing_page=true"

            expected_results.append(expected)

        # Confirm expected_results match the actual results
        assert result == expected_results
