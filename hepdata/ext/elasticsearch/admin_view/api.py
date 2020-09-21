# -*- coding: utf-8 -*-
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

from datetime import datetime, timedelta
import logging

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Document, Text, Keyword, Date, Integer, Nested, InnerDoc, Q, Index, Search
from elasticsearch_dsl.connections import connections
from flask import current_app

from hepdata.modules.records.utils.common import get_record_contents
from hepdata.modules.submission.models import HEPSubmission, DataSubmission

logging.basicConfig()
log = logging.getLogger(__name__)


class ESSubmission(Document):
    recid = Integer()
    inspire_id = Text()
    version = Integer()
    title = Text()
    collaboration = Text()
    status = Text()
    creation_date = Date()
    last_updated = Date()
    data_count = Integer()
    participants = Nested(
        properties={
            'role': Text(fields={'raw': Keyword(index='true')}),
            'full_name': Text()
        }
    )
    coordinator = Integer()

    def as_custom_dict(self, exclude=None):
        _dict_ = vars(self)

        data = _dict_['_d_']
        data['creation_date'] = data['creation_date'].strftime('%Y-%m-%d')
        data['last_updated'] = data['last_updated'].strftime('%Y-%m-%d')

        participants = data.get('participants', [])
        data['participants'] = []
        for participant in participants:
            data['participants'].append(participant['full_name'] + ' (' + participant['role'] + ')')

        if exclude:
            for field in exclude:
                if field in data:
                    del data[field]

        return data

    class Meta:
        index = 'submission'


class AdminIndexer:
    def __init__(self, *args, **kwargs):
        self.client = Elasticsearch(
            hosts=current_app.config['SEARCH_ELASTIC_HOSTS']) if 'client' not in kwargs else kwargs.get('client')

        self.index = kwargs.get('index', current_app.config['SUBMISSION_INDEX'])

        self.connections = connections
        self.connections.add_connection('default', self.client)
        self.search_fields = kwargs.get('fields',
                                        ['title', 'inspire_id', 'recid', 'collaboration', 'participants.full_name'])

    def search(self, term=None, fields=None):
        search = ESSubmission.search(using=self.client, index=self.index)[0:10000]

        if term is not None:
            if fields is None:
                fields = self.search_fields
            search = search.query(Q("multi_match", query=term, fields=fields))

        result = search.execute()

        return result

    def get_summary(self):
        s = Search(index=self.index)
        # Filter by date to approximately 20 years ago, to ensure there aren't more
        # than 10000 buckets
        date_20_years_ago = (datetime.utcnow() - timedelta(days=int(20*365.25))).date()
        s = s.filter('range', **{'last_updated': {'gte': str(date_20_years_ago)}})
        s.aggs.bucket('daily_workflows', 'date_histogram',
                      field='last_updated',
                      format="yyyy-MM-dd", interval='day') \
            .bucket('recid', 'terms', field='recid')
        result = s.execute().aggregations.to_dict()

        # flatten summary
        processed_result = []
        _daily_workflows = result['daily_workflows']
        for day in _daily_workflows['buckets']:
            for recid in day['recid']['buckets']:
                record_search = self.search(term=recid['key'], fields=['recid'])
                record = record_search[0] if len(record_search) == 1 else record_search[1]

                processed_result.append(record.as_custom_dict(exclude=[]))

        return processed_result

    def find_and_delete(self, term, fields=None):
        """
        Finds records by first searching for them, then deleting
        them all
        :param term: e.g. ATLAS
        :param fields: array of fields to search on, e.g. ['collaboration']
        :return: True
        """
        results = self.search(term, fields=fields)
        delete_count = 0
        for result in results:
            try:
                result.delete()
                delete_count += 1
            except:
                return delete_count, False

        return delete_count, True

    def index_submission(self, submission):
        participants = []

        for sub_participant in submission.participants:
            participants.append({'full_name': sub_participant.full_name, 'role': sub_participant.role})

        record_information = get_record_contents(submission.publication_recid,
                                                 submission.overall_status)

        data_count = DataSubmission.query.filter(DataSubmission.publication_recid == submission.publication_recid,
                                                 DataSubmission.version == submission.version).count()

        if record_information:
            collaboration = ','.join(record_information.get('collaborations', []))

            self.add_to_index(_id=submission.publication_recid,
                              title=record_information['title'],
                              collaboration=collaboration,
                              recid=submission.publication_recid,
                              inspire_id=submission.inspire_id,
                              status=submission.overall_status,
                              data_count=data_count,
                              creation_date=submission.created,
                              last_updated=submission.last_updated,
                              version=submission.version,
                              participants=participants,
                              coordinator=submission.coordinator)

    def reindex(self, *args, **kwargs):

        recreate = kwargs.get('recreate', False)
        if recreate:
            self.recreate_index()

        submissions = HEPSubmission.query.filter(HEPSubmission.overall_status != 'sandbox' and \
                                                 HEPSubmission.overall_status != 'sandbox_processing' and \
                                                 HEPSubmission.coordinator > 1).all()

        for submission in submissions:
            self.index_submission(submission)

    def recreate_index(self):
        """ Delete and then create a given index and set a default mapping.

        :param index: [string] name of the index. If None a default is used
        """
        submission = Index(self.index)
        submission.delete(ignore=404)

        ESSubmission.init(self.index)

    def add_to_index(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        new_sub = ESSubmission(index=self.index, **kwargs)
        return new_sub.save(index=self.index)

    def delete_from_index(self, *args, **kwargs):
        """

        :param args:
        :param kwargs: should include id
        :return:
        """
        if 'id' not in kwargs:
            raise Exception('delete_from_index expects id as a parameter. '
                            'e,g delete_from_index(id=23)')

        obj = ESSubmission.get(**kwargs)
        obj.delete()
