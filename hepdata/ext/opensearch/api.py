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
import re

from celery import shared_task
from dateutil.parser import parse
from flask import current_app
from opensearchpy.exceptions import TransportError
from opensearch_dsl import Search
from opensearch_dsl.query import QueryString, Q
from invenio_pidstore.models import RecordIdentifier
from sqlalchemy import and_
from sqlalchemy.orm import aliased


from hepdata.ext.opensearch.document_enhancers import enhance_data_document, enhance_publication_document
from .config.es_config import sort_fields_mapping, add_default_aggregations
from .utils import calculate_sort_order, prepare_author_for_indexing
from hepdata.config import CFG_PUB_TYPE, CFG_DATA_TYPE
from .query_builder import QueryBuilder, HEPDataQueryParser
from .process_results import map_result, merge_results
from invenio_db import db
import logging

from invenio_search import current_search_client as es, RecordsSearch
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import HEPSubmission, DataSubmission
from hepdata.modules.search.config import OPENSEARCH_MAX_RESULT_WINDOW, LIMIT_MAX_RESULTS_PER_PAGE


__all__ = ['search', 'index_record_ids', 'index_record_dict', 'fetch_record',
           'recreate_index', 'get_record', 'reindex_all',
           'get_n_latest_records']

logging.basicConfig()
log = logging.getLogger(__name__)


def default_index(f):
    """ Loads the default index if none is given """

    def decorator(*args, **kwargs):
        if 'index' not in kwargs:
            kwargs['index'] = current_app.config['OPENSEARCH_INDEX']
        return f(*args, **kwargs)

    decorator.__name__ = f.__name__
    return decorator


def author_index(f):
    """ Loads the default author index if none is given """

    def decorator(*args, **kwargs):
        if 'author_index' not in kwargs:
            kwargs['author_index'] = current_app.config['AUTHOR_INDEX']
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
    # Create search with preference param to ensure consistency of results across shards
    search = RecordsSearch(using=es, index=index).with_preference_param()

    if query:
        fuzzy_query = QueryString(query=query, fuzziness='AUTO')
        search.query = fuzzy_query | \
                       Q('has_child', type="child_datatable", query=fuzzy_query)

    search = search.filter("term", doc_type=CFG_PUB_TYPE)
    search = QueryBuilder.add_filters(search, filters)

    try:
        mapped_sort_field = sort_fields_mapping(sort_field)
    except ValueError as ve:
        return {'error': str(ve)}
    search = search.sort({mapped_sort_field : {"order" : calculate_sort_order(sort_order, sort_field)}})
    search = add_default_aggregations(search, filters)

    if post_filter:
        search = search.post_filter(post_filter)

    search = search.source(includes=include, excludes=exclude)
    search = search[offset:offset+size]

    try:
        pub_result = search.execute().to_dict()

        parent_filter = {
            "terms": {
                        "_id": [hit["_id"] for hit in pub_result['hits']['hits']]
            }
        }

        data_search = RecordsSearch(using=es, index=index)
        data_search = data_search.query('has_parent',
                                        parent_type="parent_publication",
                                        query=parent_filter)
        if query:
            data_search = data_search.query(QueryString(query=query))

        data_search_size = size * OPENSEARCH_MAX_RESULT_WINDOW // LIMIT_MAX_RESULTS_PER_PAGE
        data_search = data_search[0:data_search_size]
        data_result = data_search.execute().to_dict()

        merged_results = merge_results(pub_result, data_result)
        return map_result(merged_results, filters)
    except TransportError as e:
        # For search phase execution exceptions we pass the reason as it's
        # likely to be user error (e.g. invalid search query)
        if e.error == 'search_phase_execution_exception' and e.info \
                and "error" in e.info and isinstance(e.info['error'], dict):
            reason = e.info['error']['root_cause'][0]['reason']
        # Otherwise we hide the details from the user
        else:
            log.error(f'An unexpected error occurred when searching: {e}')
            reason = f'An unexpected error occurred: {e.error}'
        return { 'error': reason }


@author_index
def search_authors(name, size=20, author_index=None):
    """ Search for authors in the author index. """
    search = Search(using=es, index=author_index) \
        .query("match", full_name={"query": name, "fuzziness":"AUTO"})
    search = search[0:size]
    results = search.execute().to_dict()
    return [x['_source'] for x in results['hits']['hits']]


@default_index
@author_index
def reindex_all(index=None, author_index=None, recreate=False, update_mapping=False, batch=5, start=-1, end=-1, synchronous=False):
    """ Recreate the index and add all the records from the db to ES. """
    if recreate:
        recreate_index(index=index)
        recreate_index(index=author_index)
    elif update_mapping:
        update_record_mapping(index=index)

    # Get all finished HEPSubmission ids with max version numbers
    # by doing a left outer join of hepsubmission with itself
    h1 = aliased(HEPSubmission)
    h2 = aliased(HEPSubmission)

    # We need to compare finished versions on both sides of the join
    qry = db.session.query(h1.id) \
            .join(h2,
                  and_(h1.publication_recid == h2.publication_recid,
                       h1.version < h2.version,
                       h2.overall_status == 'finished'),
                  isouter=True) \
            .filter(h2.publication_recid == None, h1.overall_status == 'finished') \
            .order_by(h1.id)

    res = qry.all()
    ids = [x[0] for x in res]

    if ids:
        min_id = ids[0]
        max_id = ids[-1]

        if start != -1:
            start_submission = get_latest_hepsubmission(publication_recid=start)
            if start_submission and start_submission.id in ids:
                min_id = max(start_submission.id, min_id)
        if end != -1:
            end_submission = get_latest_hepsubmission(publication_recid=end)
            if end_submission and end_submission.id in ids:
                max_id = min(end_submission.id, max_id)

        # Publication recids passed in may not match order of id field
        # Swap max and min if they aren't as expected
        if max_id < min_id:
            actual_max = min_id
            min_id = max_id
            max_id = actual_max

        print('min hepsubmission id = {}'.format(min_id))
        print('max hepsubmission id = {}'.format(max_id))

        count = ids.index(min_id)
        max_index = ids.index(max_id)
        while count <= max_index:
            batch_ids = ids[count:min(count + batch, max_index + 1)]
            if synchronous:
                reindex_batch(batch_ids, index)
            else:
                print('Sending batch of IDs {0} to {1} to celery'.format(batch_ids[0], batch_ids[-1]))
                reindex_batch.delay(batch_ids, index)
            count += batch


@shared_task
def reindex_batch(hepsubmission_record_ids, index):
    log.info('Indexing records for hepsubmission IDs {0} to {1}'.format(hepsubmission_record_ids[0], hepsubmission_record_ids[-1]))
    ids = db.session.query(HEPSubmission.publication_recid, DataSubmission.associated_recid) \
        .join(DataSubmission,
              and_(HEPSubmission.publication_recid == DataSubmission.publication_recid,
                   HEPSubmission.version == DataSubmission.version),
              isouter=True) \
        .filter(HEPSubmission.id.in_(hepsubmission_record_ids), HEPSubmission.overall_status == 'finished') \
        .all()

    # ids is a list of (publication_recid, data_associated_recid) - need to flatten and remove duplicates
    rec_ids = list(set([id for result in ids for id in result if id is not None]))

    indexed_publications = []
    indexed_result = index_record_ids(rec_ids, index=index)
    indexed_publications += indexed_result[CFG_PUB_TYPE]

    log.info('Finished indexing, now pushing data keywords\n######')
    push_data_keywords(pub_ids=indexed_publications)


@default_index
def get_record(record_id, index=None):
    """ Fetch a given record from ES.

    :param record_id: [int] ES record id
    :param index: [string] name of the index. If None a default is used

    :return: [dict] Fetched record
    """
    try:
        search = RecordsSearch(using=es, index=index).source(includes="*")
        result = search.get_record(record_id).execute()
        if result.hits.total.value > 0:
            return result.hits[0].to_dict()
        else:
            return None

    except TransportError:
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
    log.info("Pushing data keywords for publication rec ids: %s", pub_ids)
    if not pub_ids:
        search = Search(using=es, index=index) \
            .filter("term", doc_type=CFG_PUB_TYPE) \
            .source(False)
        results = search.execute()
        pub_ids = [h.meta.id for h in results.hits]

    for pub_id in pub_ids:
        search = Search(using=es, index=index) \
            .query('has_parent',
                   parent_type="parent_publication",
                   query={'match': {'recid': pub_id}}) \
            .filter("term", doc_type=CFG_DATA_TYPE) \
            .source(includes=['data_keywords'])

        search = search[0:LIMIT_MAX_RESULTS_PER_PAGE]
        tables = search.execute()

        all_keywords = defaultdict(list)

        # Get keywords for all data tables
        for data_table in tables.hits:
            if hasattr(data_table, 'data_keywords'):
                for k, v in data_table.data_keywords.to_dict().items():
                    all_keywords[k].extend(v)

        # Remove duplicates
        for k, v in all_keywords.items():
            # cmenergies values are dicts so we can't just use set
            if k == 'cmenergies':
                new_value = []
                for val in v:
                    if val not in new_value:
                        new_value.append(val)
            else:
                new_value = list(set(v))
            all_keywords[k] = new_value

        body = {
            "doc": {
                'data_keywords': dict(all_keywords)
            }
        }

        try:
            es.update(index=index, id=pub_id, body=body, retry_on_conflict=3)
        except Exception as e:
            log.error(e)


@default_index
def index_record_ids(record_ids, index=None):
    """ Index records given in the argument.

    :param record_ids: [list of ints] list of record ids e.g. [1, 5, 2, 3]
    :param index: [string] name of the index. If None a default is used
    :return: list of indexed publication and data recids
    """
    from hepdata.modules.records.utils.common import get_record_by_id

    docs = list(filter(None, [get_record_by_id(recid) for recid in record_ids]))

    existing_record_ids = [doc['recid'] for doc in docs]
    log.info('Indexing existing record IDs: {}'.format(existing_record_ids))

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
                log.warning('Skipping unfinished record ID {}'.format(doc['recid']))
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
    from .config.record_mapping import mapping

    body = {
        "mappings": {
            "properties": mapping
        }
    }

    es.indices.delete(index=index, ignore=404)
    es.indices.create(index=index, body=body)


@default_index
def update_record_mapping(index=None):
    """ Updates the default record mapping for the given index

    :param index: [string] name of the index. If None a default is used
    """
    from .config.record_mapping import mapping

    body = { "properties": mapping }
    try:
        es.indices.put_mapping(index=index, body=body)
    except TransportError as e:
        msg = e.info.get('error',{}).get('root_cause',[{}])[0].get('reason')
        raise ValueError(f"Unable to update record mapping: {msg}\nYou may need to recreate the index to update the mapping.")


@default_index
def fetch_record(record_id, doc_type, index=None):
    """ Fetch a record from ES with a given id.

    :param record_id: [int]
    :param doc_type: [string] document type
    :param index: [string] name of the index. If None a default is used

    :return: [dict] Record if found, otherwise an error message
    """
    res = es.get(index=index, id=record_id)
    return res.get('_source', res)


@default_index
def get_n_latest_records(n_latest, field="last_updated", index=None):
    """ Gets latest N records from the index """

    search = Search(using=es, index=index) \
        .filter("term", doc_type=CFG_PUB_TYPE) \
        .sort({field: {"order": "desc"}}) \
        .source(excludes=["authors", "keywords"])
    search = search[0:n_latest]

    query_result = search.execute().to_dict()
    return query_result['hits']['hits']


@default_index
def get_count_for_collection(doc_type, index=None):
    """

    :param doc_type: e.g. CFG_PUB_TYPE or CFG_DATA_TYPE
    :param index: name of index to use.
    :return: the number of records in that collection
    """
    return es.count(index=index, q='doc_type:'+doc_type)


@default_index
def get_all_ids(index=None, id_field='recid', last_updated=None, latest_first=False):
    """Get all record or inspire ids of publications in the search index

    :param index: name of index to use.
    :param id_field: elasticsearch field to return. Should be 'recid' or 'inspire_id'
    :return: list of integer ids
    """
    if id_field not in ('recid', 'inspire_id'):
        raise ValueError('Invalid ID field %s' % id_field)

    search = Search(using=es, index=index) \
        .filter("term", doc_type=CFG_PUB_TYPE) \
        .source(fields=[id_field])

    if last_updated:
        search = search.filter("range", **{'last_updated': {'gte': last_updated.isoformat()}})

    if latest_first:
        search = search.sort({'last_updated' : {'order' : 'desc'}})
    else:
        search = search.sort('recid')

    search = search.params(preserve_order=True)

    return [int(h[id_field]) for h in search.scan()]
