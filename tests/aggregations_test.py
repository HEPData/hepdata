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
from hepdata.ext.elasticsearch.aggregations import parse_author_aggregations, \
    parse_date_aggregations, parse_collaboration_aggregations, \
    parse_other_facets, parse_aggregations, parse_cmenergies_aggregations, \
    create_dummy_cmenergies_facets


def test_parse_author_aggregations():
    buckets = [
        {'key': 'author1', 'doc_count': 1},
        {'key': 'author2', 'doc_count': 2}
    ]

    expected = {
        'vals': [
            {
                'url_params': {'author': 'author1'},
                'key': 'author1',
                'doc_count': 1
            },
            {
                'url_params': {'author': 'author2'},
                'key': 'author2',
                'doc_count': 2
            }
        ],
        'max_values': 10,
        'printable_name': 'Authors',
        'type': 'author'
    }
    assert(parse_author_aggregations(buckets) == expected)


def test_parse_cmenergies_aggregations_simple():
    buckets = [
        {'key': 0.0, 'doc_count': 13},
        {'key': 10.0, 'doc_count': 50},
        {'key': 20.0, 'doc_count': 27}
    ]

    expected = {
        'vals': [
            {
                'url_params': {'cmenergies': '0.0,10.0'},
                'key': u"0.0 \u2264 \u221As < 10.0",
                'doc_count': 13
            },
            {
                'url_params': {'cmenergies': '10.0,20.0'},
                'key': u"10.0 \u2264 \u221As < 20.0",
                'doc_count': 50
            },
            {
                'url_params': {'cmenergies': '20.0,100000.0'},
                'key': u"\u221As \u2265 20.0",
                'doc_count': 27
            }
        ],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(parse_cmenergies_aggregations(buckets) == expected)


def test_parse_cmenergies_aggregations_filtered():
    buckets = [
        {'key': 10.0, 'doc_count': 13},
        {'key': 11.0, 'doc_count': 50},
        {'key': 12.0, 'doc_count': 27}
    ]
    query_filters1 = [('cmenergies', [10.0, 15.0])]
    expected1 = {
        'vals': [
            {
                'url_params': {'cmenergies': '10.0,11.0'},
                'key': u"10.0 \u2264 \u221As < 11.0",
                'doc_count': 13
            },
            {
                'url_params': {'cmenergies': '11.0,12.0'},
                'key': u"11.0 \u2264 \u221As < 12.0",
                'doc_count': 50
            },
            {
                'url_params': {'cmenergies': '12.0,15.0'},
                'key': u"12.0 \u2264 \u221As < 15.0",
                'doc_count': 27
            }
        ],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(parse_cmenergies_aggregations(buckets, query_filters1) == expected1)

    buckets = [
        {'key': 10.0, 'doc_count': 13},
        {'key': 11.0, 'doc_count': 50},
        {'key': 12.0, 'doc_count': 27}
    ]
    query_filters2 = [('cmenergies', [11.0, 12.0])]
    expected2 = {
        'vals': [
            {
                'url_params': {'cmenergies': '11.0,12.0'},
                'key': u"11.0 \u2264 \u221As < 12.0",
                'doc_count': 50
            }
        ],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(parse_cmenergies_aggregations(buckets, query_filters2) == expected2)


def test_parse_collaboration_aggregations():
    buckets = [
        {'key': 'collab1', 'doc_count': 3},
        {'key': 'collab2', 'doc_count': 1}
    ]
    expected = {
        'vals': [
            {
                'url_params': {'collaboration': 'collab1'},
                'key': 'COLLAB1',
                'doc_count': 3
            },
            {
                'url_params': {'collaboration': 'collab2'},
                'key': 'COLLAB2',
                'doc_count': 1
            }
        ],
        'max_values': 5,
        'printable_name': 'Collaboration',
        'type': 'collaboration'
    }
    assert(parse_collaboration_aggregations(buckets) == expected)

def test_parse_date_aggregations():
    buckets = [
        {
            'key_as_string': '2013-01-01T00:00:00.000Z',
            'key': 1356998400000,
            'doc_count': 1
        },
        {
            'key_as_string': '2014-02-01T00:00:00.000Z',
            'key': 1391212800000,
            'doc_count': 1
        },
        {
            'key_as_string': '2014-01-01T00:00:00.000Z',
            'key': 1388534400000,
            'doc_count': 2
        }
    ]

    expected = {
        'vals': [
            {
                'url_params': {'date': 2014},
                'key': 2014,
                'key_as_string': '2014-01-01T00:00:00.000Z',
                'doc_count': 2
            },
            {
                'url_params': {'date': 2014},
                'key': 2014,
                'key_as_string': '2014-02-01T00:00:00.000Z',
                'doc_count': 1
            },
            {
                'url_params': {'date': 2013},
                'key': 2013,
                'key_as_string': '2013-01-01T00:00:00.000Z',
                'doc_count': 1
            }
        ],
        'max_values': 5,
        'printable_name': 'Date',
        'type': 'date'
    }

    assert(parse_date_aggregations(buckets) == expected)

def test_parse_other_facets():
    buckets = [
        {'key': 'Key1', 'doc_count': 1},
        {'key': 'Key2', 'doc_count': 3},
        {'key': 'Key3', 'doc_count': 2}
    ]
    expected = {
        'vals': [
            {
                'url_params': {'test_facet': 'Key1'},
                'key': 'Key1',
                'doc_count': 1
            },
            {
                'url_params': {'test_facet': 'Key2'},
                'key': 'Key2',
                'doc_count': 3
            },
            {
                'url_params': {'test_facet': 'Key3'},
                'key': 'Key3',
                'doc_count': 2
            }
        ],
        'max_values': 5,
        'printable_name': 'Test_facet',
        'type': 'test_facet'
    }
    assert(parse_other_facets(buckets, 'test_facet') == expected)


def test_parse_aggregations():
    aggregations = {
        'nested_authors': {
            'author_full_names': {
                'buckets': [
                    {'key': 'author1', 'doc_count': 1}
                ]
            }
        },
        # 'cmenergies': {
        #     'buckets': [
        #         {'key': 10.0, 'doc_count': 13}
        #     ]
        # },
        'collaboration': {
            'buckets': [
                {'key': 'collab1', 'doc_count': 3}
            ],
        },
        'dates': {
            'buckets': [
                {
                    'key_as_string': '2013-01-01T00:00:00.000Z',
                    'key': 1356998400000,
                    'doc_count': 1
                }
            ]
        },
        'another_facet': {
            'buckets': [
                {'key': 'Key1', 'doc_count': 1}
            ]
        },
    }

    expected = [
        {
            'vals': [
                {
                    'url_params': {'date': 2013},
                    'key': 2013,
                    'key_as_string': '2013-01-01T00:00:00.000Z',
                    'doc_count': 1
                }
            ],
            'max_values': 5,
            'printable_name': 'Date',
            'type': 'date'
        },
        {
            'vals': [
                {
                    'url_params': {'author': 'author1'},
                    'key': 'author1',
                    'doc_count': 1
                }
            ],
            'max_values': 10,
            'printable_name': 'Authors',
            'type': 'author'
        },
        {
            'vals': [
                {
                    'url_params': {'another_facet': 'Key1'},
                    'key': 'Key1',
                    'doc_count': 1
                }
            ],
            'max_values': 5,
            'printable_name': 'Another_facet',
            'type': 'another_facet'
        },
        {
            'vals': [
                {
                    'url_params': {'collaboration': 'collab1'},
                    'key': 'COLLAB1',
                    'doc_count': 3
                }
            ],
            'max_values': 5,
            'printable_name': 'Collaboration',
            'type': 'collaboration'
        },
        {
            'vals': [
                {'doc_count': None,
                 'key': u'0.0 \u2264 \u221as < 1.0',
                 'url_params': {'cmenergies': '0.0,1.0'}},
                {'doc_count': None,
                 'key': u'1.0 \u2264 \u221as < 2.0',
                 'url_params': {'cmenergies': '1.0,2.0'}},
                {'doc_count': None,
                 'key': u'2.0 \u2264 \u221as < 5.0',
                 'url_params': {'cmenergies': '2.0,5.0'}},
                {'doc_count': None,
                 'key': u'5.0 \u2264 \u221as < 10.0',
                 'url_params': {'cmenergies': '5.0,10.0'}},
                {'doc_count': None,
                 'key': u'10.0 \u2264 \u221as < 100.0',
                 'url_params': {'cmenergies': '10.0,100.0'}},
                {'doc_count': None,
                 'key': u'100.0 \u2264 \u221as < 1000.0',
                 'url_params': {'cmenergies': '100.0,1000.0'}},
                {'doc_count': None,
                 'key': u'1000.0 \u2264 \u221as < 7000.0',
                 'url_params': {'cmenergies': '1000.0,7000.0'}},
                {'doc_count': None,
                 'key': u'7000.0 \u2264 \u221as < 8000.0',
                 'url_params': {'cmenergies': '7000.0,8000.0'}},
                {'doc_count': None,
                 'key': u'8000.0 \u2264 \u221as < 13000.0',
                 'url_params': {'cmenergies': '8000.0,13000.0'}},
                {'doc_count': None,
                 'key': u'\u221as \u2265 13000.0',
                 'url_params': {'cmenergies': '13000.0,100000.0'}}],
            'max_values': 5,
            'printable_name': 'CM Energies (GeV)',
            'type': 'cmenergies'
        }
    ]

    parsed_aggregations = parse_aggregations(aggregations)
    assert(len(parsed_aggregations) == len(expected))

    for agg in parsed_aggregations:
        assert(agg in expected)


def test_create_dummy_cmenergies_facets():
    expected = {
        'vals': [
            {'doc_count': None,
             'key': u'0.0 \u2264 \u221as < 1.0',
             'url_params': {'cmenergies': '0.0,1.0'}},
            {'doc_count': None,
             'key': u'1.0 \u2264 \u221as < 2.0',
             'url_params': {'cmenergies': '1.0,2.0'}},
            {'doc_count': None,
             'key': u'2.0 \u2264 \u221as < 5.0',
             'url_params': {'cmenergies': '2.0,5.0'}},
            {'doc_count': None,
             'key': u'5.0 \u2264 \u221as < 10.0',
             'url_params': {'cmenergies': '5.0,10.0'}},
            {'doc_count': None,
             'key': u'10.0 \u2264 \u221as < 100.0',
             'url_params': {'cmenergies': '10.0,100.0'}},
            {'doc_count': None,
             'key': u'100.0 \u2264 \u221as < 1000.0',
             'url_params': {'cmenergies': '100.0,1000.0'}},
            {'doc_count': None,
             'key': u'1000.0 \u2264 \u221as < 7000.0',
             'url_params': {'cmenergies': '1000.0,7000.0'}},
            {'doc_count': None,
             'key': u'7000.0 \u2264 \u221as < 8000.0',
             'url_params': {'cmenergies': '7000.0,8000.0'}},
            {'doc_count': None,
             'key': u'8000.0 \u2264 \u221as < 13000.0',
             'url_params': {'cmenergies': '8000.0,13000.0'}},
            {'doc_count': None,
             'key': u'\u221as \u2265 13000.0',
             'url_params': {'cmenergies': '13000.0,100000.0'}}],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(create_dummy_cmenergies_facets() == expected)

    expected_filtered1 = {
        'vals': [
            {'doc_count': None,
             'key': u'1.0 \u2264 \u221as < 2.0',
             'url_params': {'cmenergies': '1.0,2.0'}}
        ],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(create_dummy_cmenergies_facets([('cmenergies', [1.0, 2.0])]) == expected_filtered1)

    expected_filtered2 = {
        'vals': [
            {'doc_count': None,
             'key': u'1000.0 \u2264 \u221as < 2000.0',
             'url_params': {'cmenergies': '1000.0,2000.0'}},
            {'doc_count': None,
             'key': u'2000.0 \u2264 \u221as < 3000.0',
             'url_params': {'cmenergies': '2000.0,3000.0'}},
            {'doc_count': None,
             'key': u'3000.0 \u2264 \u221as < 4000.0',
             'url_params': {'cmenergies': '3000.0,4000.0'}},
            {'doc_count': None,
             'key': u'4000.0 \u2264 \u221as < 5000.0',
             'url_params': {'cmenergies': '4000.0,5000.0'}},
            {'doc_count': None,
             'key': u'5000.0 \u2264 \u221as < 6000.0',
             'url_params': {'cmenergies': '5000.0,6000.0'}},
            {'doc_count': None,
             'key': u'6000.0 \u2264 \u221as < 7000.0',
             'url_params': {'cmenergies': '6000.0,7000.0'}},
        ],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(create_dummy_cmenergies_facets([('cmenergies', [1000.0, 7000.0])]) == expected_filtered2)

    expected_filtered3 = {
        'vals': [],
        'max_values': 5,
        'printable_name': 'CM Energies (GeV)',
        'type': 'cmenergies'
    }
    assert(create_dummy_cmenergies_facets([('cmenergies', [1000.0, 1000.0])]) == expected_filtered3)
    assert(create_dummy_cmenergies_facets([('cmenergies', [1000.0])]) == expected_filtered3)
