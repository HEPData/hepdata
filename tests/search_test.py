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
from hepdata.ext.elasticsearch.config.es_config import default_sort_order_for_field
from hepdata.ext.elasticsearch.process_results import merge_results, match_tables_to_papers, \
    get_basic_record_information, is_datatable
from hepdata.ext.elasticsearch.query_builder import QueryBuilder, HEPDataQueryParser
from hepdata.ext.elasticsearch.utils import flip_sort_order, parse_and_format_date, prepare_author_for_indexing, \
    calculate_sort_order, push_keywords


def test_query_builder_generate_query():
    query_string1 = QueryBuilder.generate_query_string('')
    assert (query_string1 == {"match_all": {}})

    _test_query = "observables:ASYM"
    query_string2 = QueryBuilder.generate_query_string(_test_query)
    assert (query_string2 == {'query_string': {'query': 'observables:ASYM', 'fuzziness': 'AUTO'}})


def test_query_builder_generate_nested_query():
    _test_query = "observables:ASYM"
    nested_query = QueryBuilder.generate_nested_query('test_path', _test_query)
    expected = {
        "nested": {
            "path": 'test_path',
            "query": {'query_string': {'query': 'observables:ASYM', 'fuzziness': 'AUTO'}}
        }
    }
    assert (nested_query == expected)


def test_query_builder_constructor():
    qb = QueryBuilder()
    assert(qb is not None)
    assert(qb.query == {'query': {'bool': {'must': {'match_all': {}}}}})


def test_query_builder_sorting():
    qb = QueryBuilder()
    qb.add_sorting('title')
    assert(qb.query == {'sort': [{'title.raw': {'order': 'asc'}}],
                        'query': {'bool': {'must': {'match_all': {}}}}})

    qb.add_sorting('date', 'rev')
    assert(qb.query == {'sort': [{'creation_date': {'order': 'asc'}}],
                        'query': {'bool': {'must': {'match_all': {}}}}})


def test_query_builder_source_filter():
    qb = QueryBuilder()
    qb.add_source_filter('test_includes', 'test_excludes')
    assert(qb.query == {
        '_source': {'includes': 'test_includes', 'excludes': 'test_excludes'},
        'query': {'bool': {'must': {'match_all': {}}}}
    })


def test_query_builder_pagination():
    qb = QueryBuilder()
    qb.add_pagination(5)
    assert(qb.query == {
        'size': 5,
        'from': 0,
        'query': {'bool': {'must': {'match_all': {}}}}
    })

    qb.add_pagination(7, 3)
    assert(qb.query == {
        'size': 7,
        'from': 3,
        'query': {'bool': {'must': {'match_all': {}}}}
    })


def test_query_builder_child_parent_relation():
    qb = QueryBuilder()
    qb.add_child_parent_relation("test_type")
    assert(qb.query == {
        'query': {
            'bool': {
                'should': [
                    {
                        'has_child': {
                            'parent_type': 'test_type',
                            'query': {}
                        }
                    }
                ]
            }
        }
    })


def test_query_builder_add_aggregations():
    qb = QueryBuilder()
    qb.add_aggregations()
    assert(qb.query == {
        'aggs': {
            'cmenergies': {'terms': {'field': 'data_keywords.cmenergies.raw'}},
            'collaboration': {'terms': {'field': 'collaborations.raw'}},
            'dates': {'date_histogram': {'field': 'publication_date',  'interval': 'year'}},
            'nested_authors': {'aggs': {
                'author_full_names': {'terms': {'field': 'authors.full_name'}}},
                'nested': {'path': 'authors'}
            },
            'observables': {'terms': {'field': 'data_keywords.observables.raw'}},
            'phrases': {'terms': {'field': 'data_keywords.phrases.raw'}},
            'reactions': {'terms': {'field': 'data_keywords.reactions.raw'}},
            'subject_areas': {'terms': {'field': 'subject_area.raw'}}
        },
        'query': {'bool': {'must': {'match_all': {}}}}
    })


def test_query_builder_add_filters():
    qb = QueryBuilder()
    qb.add_filters([('author', 'test_author')])
    assert(qb.query == {
        "query": {
            "nested": {
                "path": "authors",
                "query": {
                    "bool": {
                        "must": {
                            "match": {
                                "authors.full_name": "test_author"
                            }
                        }
                    }
                }
            }
        }
    })


def test_query_builder_add_post_filter():
    qb = QueryBuilder()
    qb.add_post_filter(None)
    assert(qb.query == {'query': {'bool': {'must': {'match_all': {}}}}})

    qb.add_post_filter('test_postfilter')
    assert(qb.query == {
        'query': {'bool': {'must': {'match_all': {}}}},
        'post_filter': 'test_postfilter'
    })


def test_query_parser():
    _test_query = "observables:ASYM"
    parsed_query_string = HEPDataQueryParser.parse_query(_test_query)
    assert (parsed_query_string == "data_keywords.observables:ASYM")

    _test_query2 = "observables:ASYM AND phrases:Elastic Scattering OR cmenergies:1.34"
    parsed_query_string2 = HEPDataQueryParser.parse_query(_test_query2)

    print(parsed_query_string2)

    assert (parsed_query_string2 == "data_keywords.observables:ASYM "
                                    "AND data_keywords.phrases:Elastic Scattering "
                                    "OR data_keywords.cmenergies:1.34")


def test_search():
    """
    Test the search functions work correctly, also with the new query syntax.
    :return:
    """
    pass


def test_merge_results():
    source_a = {"hits": {"hits": [{"key": "testa"}], "total": 1}}
    source_b = {"hits": {"hits": [{"key": "testb"}], "total": 1}}

    merged = merge_results(source_a, source_b)
    assert ("hits" in merged)
    assert (len(merged["hits"]) == 2)
    assert (merged["total"] == 1)


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
            print(results["data_keywords"])
            assert (len(results["data_keywords"]["reaction"]) == 2)
            assert (results["data_keywords"]["reaction"][0] == "PP --> PP")
            assert (results["data_keywords"]["reaction"][1] == "PP --> PX")

    try:
        push_keywords([])
    except ValueError as ve:
        assert (ve)


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
         "keywords": [""]},

        {"_id": 4, "recid": 4, "authors": [], "title": "Test 2",
         "keywords": [""]}

    ]

    tables = [
        {"recid": 2, "_source": {"related_publication": 1, "title": "Table1",
                                 "keywords": [{"name": "reaction", "value": "PP --> PP"}]}},
        {"recid": 3, "_source": {"related_publication": 1, "title": "Table2",
                                 "keywords": [{"name": "reaction", "value": "PP --> PX"}]}}
    ]

    aggregated = match_tables_to_papers(tables, papers)

    assert (aggregated is not [])
    assert (len(aggregated) == 2)
    print(aggregated)


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
    assert (is_datatable({"doc_type": "datatable"}))
    assert (not is_datatable({"doc_type": "publication"}))
