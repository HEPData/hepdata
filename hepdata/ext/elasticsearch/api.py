#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
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
from __future__ import print_function

from collections import defaultdict
import time

from dateutil.parser import parse
from flask import current_app
from elasticsearch.exceptions import NotFoundError, RequestError
from invenio_pidstore.models import RecordIdentifier
from sqlalchemy import func

from hepdata.ext.elasticsearch.document_enhancers import enhance_data_document, enhance_publication_document
from .utils import prepare_author_for_indexing
from hepdata.config import CFG_PUB_TYPE, CFG_DATA_TYPE
from query_builder import QueryBuilder, HEPDataQueryParser
from process_results import map_result, merge_results
from invenio_db import db
import logging

from invenio_search import current_search_client as es

__all__ = ['search', 'index_record_ids', 'index_record_dict', 'fetch_record',
           'recreate_index', 'get_record', 'reindex_all',
           'get_n_latest_records']

logging.basicConfig()
log = logging.getLogger(__name__)


def default_index(f):
    """ Loads the default index if none is given """

    def decorator(*args, **kwargs):
        if 'index' not in kwargs:
            kwargs['index'] = current_app.config['ELASTICSEARCH_INDEX']
        return f(*args, **kwargs)

    decorator.__name__ = f.__name__
    return decorator


@default_index
def search(query,
           index=None,
           filters=list(),
           size=10,
           include="*",
           exclude="authors",
           offset=0,
           sort_field=None,
           sort_order='',
           post_filter=None):
    """ Perform a search query.

    :param query: [string] query string e.g. 'higgs boson'
    :param index: [string] name of the index. If None a default is used
    :param filters: [list of tuples] list of filters for the query.
                    Currently supported: ('author', author_fullname),
                    ('collaboration', collaboration_name), ('date', date)
    :param size: [int] max number of hits that should be returned
    :param offset: [int] offset for the results (used for pagination)
    :param sort_by: [string] sorting field. Currently supported fields:
                    "title", "collaboration", "date", "relevance"
    :param sort_order: [string] order of the sorting either original
                    (for a particular field) or reversed. Supported:
                    '' or 'rev'

    :return: [dict] dictionary with processed results and facets
    """
    # If empty query then sort by date
    if query == '' and not sort_field:
        sort_field = 'date'

    query = HEPDataQueryParser.parse_query(query)

    # Build core query
    data_query = QueryBuilder.generate_query_string(query)
    pub_query = QueryBuilder.generate_query_string(query)
    authors_query = QueryBuilder.generate_nested_query('authors', query)

    query_builder = QueryBuilder()
    query_builder.add_child_parent_relation(CFG_DATA_TYPE,
                                            relation="child",
                                            related_query=data_query,
                                            other_queries=[pub_query,
                                                           authors_query])

    # Add additional options
    query_builder.add_pagination(size=size, offset=offset)
    query_builder.add_sorting(sort_field=sort_field, sort_order=sort_order)
    query_builder.add_filters(filters)
    query_builder.add_post_filter(post_filter)
    query_builder.add_aggregations()
    query_builder.add_source_filter(include, exclude)

    if query:
        # Randomize search among the available shard copies.
        pub_result = es.search(index=index,
                               body=query_builder.query,
                               doc_type=CFG_PUB_TYPE)
    else:
        # Execute search only on the primary shards (to ensure no missing or duplicate results).
        pub_result = es.search(index=index,
                               body=query_builder.query,
                               doc_type=CFG_PUB_TYPE,
                               preference="_primary")

    parent_filter = {
        "filtered": {
            "filter": {
                "terms": {
                    "_id": [hit["_id"] for hit in pub_result['hits']['hits']]
                }
            }
        }
    }

    query_builder = QueryBuilder()
    query_builder.add_child_parent_relation(CFG_PUB_TYPE,
                                            relation="parent",
                                            related_query=parent_filter,
                                            must=True,
                                            other_queries=[data_query])
    query_builder.add_pagination(size=size * 50)

    data_result = es.search(index=index,
                            body=query_builder.query,
                            doc_type=CFG_DATA_TYPE)

    merged_results = merge_results(pub_result, data_result)

    return map_result(merged_results)


def search_authors(name, size=20):
    """ Search for authors in the author index. """
    from hepdata.config import CFG_ES_AUTHORS
    index, doc_type = CFG_ES_AUTHORS

    query = {
        "size": size,
        "query": {
            "match": {
                "full_name": {
                    "query": name,
                    "fuzziness": "AUTO"
                }
            }
        }
    }

    results = es.search(index=index, doc_type=doc_type, body=query)
    return [x['_source'] for x in results['hits']['hits']]


@default_index
def reindex_all(index=None, recreate=False, batch=50, start=-1, end=-1):
    """ Recreate the index and add all the records from the db to ES. """

    if recreate:
        recreate_index(index=index)

    qry = db.session.query(func.max(RecordIdentifier.recid).label("max_recid"),
                           func.min(RecordIdentifier.recid).label("min_recid"),
                           )
    res = qry.one()
    min_recid = res.min_recid
    max_recid = res.max_recid

    if max_recid and min_recid:

        if start != -1:
            min_recid = max(start, min_recid)
        if end != -1:
            max_recid = min(end, max_recid)
        print('min_recid = {}'.format(min_recid))
        print('max_recid = {}'.format(max_recid))

        count = min_recid
        while count <= max_recid:
            print('Indexing record IDs {0} to {1}'.format(count, min(count + batch - 1, max_recid)))
            indexed_publications = []
            rec_ids = range(count, min(count + batch, max_recid + 1))
            indexed_result = index_record_ids(rec_ids, index=index)
            indexed_publications += indexed_result[CFG_PUB_TYPE]
            count += batch

            print('Finished indexing, now pushing data keywords\n######')
            push_data_keywords(pub_ids=indexed_publications)


@default_index
def get_record(record_id, doc_type, index=None, parent=None):
    """ Fetch a given record from ES.
    Parent must be defined for fetching datatable records.

    :param record_id: [int] ES record id
    :param doc_type: [string] type of document. "publication" or "datatable"
    :param index: [string] name of the index. If None a default is used
    :param parent: [int] record id of the potential parent

    :return: [dict] Fetched record
    """
    try:
        if doc_type == CFG_DATA_TYPE and parent:
            result = es.get(index=index, doc_type=doc_type,
                            id=record_id, parent=parent)
        else:
            result = es.get(index=index, doc_type=doc_type, id=record_id)

        return result.get('_source', result)
    except (NotFoundError, RequestError):
        return None


@default_index
def get_records_matching_field(field, id, index=None, doc_type=None, source=None):
    """ Checks if a record with a given ID exists in the index """

    query = {
        "size": 9999,
        'query': {
            "bool": {
                "must": [
                    {
                        "match": {
                            field: id
                        }
                    }
                ]
            }
        }
    }

    if doc_type:
        query["query"]["bool"]["must"].append({
            "match": {
                "doc_type": doc_type
            }
        })

    if source:
        query["_source"] = source

    print(query)

    return es.search(index=index, body=query)


@default_index
def delete_item_from_index(id, index, doc_type, parent=None):
    """
    Given an id, deletes an item from the index.
    :param id:
    :param index:
    :param doc_type:
    :param parent: the parent record id
    :return:
    """
    if parent:
        es.delete(index=index, id=id, routing=parent)
    else:
        es.delete(index=index, id=id, routing=id)


@default_index
def push_data_keywords(pub_ids=None, index=None):
    """ Go through all the publications and their datatables and move data
     keywords from tables to their parent publications. """
    if not pub_ids:
        body = {'query': {'match_all': {}}}
        results = es.search(index=index,
                            doc_type=CFG_PUB_TYPE,
                            body=body,
                            _source=False)
        pub_ids = [i['_id'] for i in results['hits']['hits']]

    for pub_id in pub_ids:
        query_builder = QueryBuilder()
        query_builder.add_child_parent_relation(
            'parent_publication',
            relation='parent',
            must=True,
            related_query={'match': {'recid': pub_id}}
        )

        tables = es.search(
            index=index,
            body=query_builder.query,
            _source_includes='keywords'
        )

        keywords = [d['_source'].get('keywords', None)
                    for d in tables['hits']['hits']]

        # Flatten the list
        keywords = [i for inner in keywords for i in inner]

        # Aggregate
        agg_keywords = defaultdict(list)
        for kw in keywords:
            agg_keywords[kw['name']].append(kw['value'])

        # Remove duplicates
        for k, v in agg_keywords.items():
            agg_keywords[k] = list(set(v))

        body = {
            "doc": {
                'data_keywords': dict(agg_keywords)
            }
        }

        try:
            es.update(index=index, id=pub_id, body=body)
        except Exception as e:
            log.error(e.message)


@default_index
def index_record_ids(record_ids, index=None):
    """ Index records given in the argument.

    :param record_ids: [list of ints] list of record ids e.g. [1, 5, 2, 3]
    :param index: [string] name of the index. If None a default is used
    :return: list of indexed publication and data recids
    """
    from hepdata.modules.records.utils.common import get_record_by_id

    docs = filter(None, [get_record_by_id(recid) for recid in record_ids])

    existing_record_ids = [doc['recid'] for doc in docs]
    print('Indexing existing record IDs:', existing_record_ids)

    to_index = []
    indexed_result = {CFG_DATA_TYPE: [], CFG_PUB_TYPE: []}

    for doc in docs:
        if 'related_publication' in doc:
            # Remove unnecessary fields if it's a data record
            for field in ['authors', '_additional_authors', '_first_author']:
                if field in doc:
                    del doc[field]

            enhance_data_document(doc)

            op_dict = {
                "index": {
                    "_index": index,
                    "_id": doc['recid'],
                    "routing": doc['related_publication']
                }
            }

            indexed_result[CFG_DATA_TYPE].append(doc['recid'])
            to_index.append(op_dict)

        else:

            if 'version' not in doc:
                print('Skipping unfinished record ID {}'.format(doc['recid']))
                continue

            author_docs = prepare_author_for_indexing(doc)
            to_index += author_docs

            enhance_publication_document(doc)

            op_dict = {
                "index": {
                    "_index": index,
                    "_id": doc['recid'],
                    "routing": doc['recid']
                }
            }

            indexed_result[CFG_PUB_TYPE].append(doc['recid'])
            to_index.append(op_dict)

        if doc["last_updated"] is not None:
            doc["last_updated"] = parse(doc["last_updated"]).isoformat()
        to_index.append(doc)

    if to_index:
        result = es.bulk(index=index, body=to_index, refresh=True)
        if result['errors']:
            log.error('Bulk insert failed: %s' % result)

    return indexed_result


@default_index
def index_record_dict(record_dict, doc_type, recid, index=None, parent=None):
    """ Index a given document

    :param record_dict: [dict] A python dictionary containing
    a JSON-like structure which needs to be indexed
    :param doc_type: [string] type of document. "publication" or "datatable"
    :param index: [string] name of the index. If None a default is used
    :param parent: [int] record id of the potential parent

    :return: [dict] Response dictionary
    """
    if parent:
        return es.index(index=index,
                        doc_type=doc_type,
                        id=recid,
                        body=record_dict,
                        parent=parent)
    else:
        return es.index(index=index,
                        doc_type=doc_type,
                        id=recid,
                        body=record_dict)


@default_index
def recreate_index(index=None):
    """ Delete and then create a given index and set a default mapping.

    :param index: [string] name of the index. If None a default is used
    """
    from config.record_mapping import mapping

    body = {
        "mappings": {
            "properties": mapping
        }
    }

    es.indices.delete(index=index, ignore=404)
    es.indices.create(index=index, body=body)


@default_index
def fetch_record(record_id, doc_type, index=None):
    """ Fetch a record from ES with a given id.

    :param record_id: [int]
    :param doc_type: [string] document type
    :param index: [string] name of the index. If None a default is used

    :return: [dict] Record if found, otherwise an error message
    """
    res = es.get(index=index, doc_type=doc_type, id=record_id)
    return res.get('_source', res)


@default_index
def get_n_latest_records(n_latest, field="last_updated", index=None):
    """ Gets latest N records from the index """

    query = {
        "size": n_latest,
        "query": QueryBuilder.generate_query_string(),
        "sort": [{
            field: {
                "order": "desc"
            }
        }],
        "_source": {"exclude": ["authors", "keywords"]}
    }

    query_result = es.search(index=index, doc_type=CFG_PUB_TYPE, body=query)
    return query_result['hits']['hits']


@default_index
def get_count_for_collection(doc_type, index=None):
    """

    :param doc_type: e.g. CFG_PUB_TYPE or CFG_DATA_TYPE
    :param index: name of index to use.
    :return: the number of records in that collection
    """
    return es.count(index=index, doc_type=doc_type)
