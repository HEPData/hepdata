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

from datetime import datetime
import logging

from opensearchpy import OpenSearch
from opensearch_dsl import Document, Text, Keyword, Date, Integer, Nested, Q, Index
from opensearch_dsl.connections import connections
from flask import current_app

from hepdata.modules.permissions.models import CoordinatorRequest
from hepdata.modules.records.utils.common import get_record_contents
from hepdata.modules.submission.api import get_submission_participants_for_record
from hepdata.modules.submission.models import HEPSubmission, DataSubmission

logging.basicConfig()
log = logging.getLogger(__name__)


class OSSubmission(Document):
    recid = Integer()
    inspire_id = Text()
    arxiv_id = Text()
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
    coordinator_group = Text()

    def as_custom_dict(self, exclude=None, flatten_participants=True):
        _dict_ = vars(self)

        data = _dict_['_d_']
        data['creation_date'] = data['creation_date'].strftime('%Y-%m-%d')
        data['last_updated'] = data['last_updated'].strftime('%Y-%m-%d')

        participants = data.get('participants', [])
        if flatten_participants:
            data['participants'] = []
            for participant in participants:
                data['participants'].append(participant['full_name'] + ' (' + participant['role'] + ')')
        else:
            data['participants'] = [p.to_dict() for p in participants]

        if exclude:
            for field in exclude:
                if field in data:
                    del data[field]

        return data

    class Meta:
        index = 'submission'


class AdminIndexer:

    # We don't index or retrieve values with date earlier than EXCLUDE_BEFORE_DATE
    # unless in TESTING mode
    EXCLUDE_BEFORE_DATE = datetime(2017, 1, 1)

    def __init__(self, *args, **kwargs):
        self.client = OpenSearch(
            hosts=current_app.config['SEARCH_HOSTS']) if 'client' not in kwargs else kwargs.get('client')

        self.index = kwargs.get('index', current_app.config['SUBMISSION_INDEX'])

        self.connections = connections
        self.connections.add_connection('default', self.client)
        self.search_fields = kwargs.get('fields',
                                        ['title', 'inspire_id', 'recid', 'collaboration', 'participants.full_name'])

    def search(self, term=None, fields=None):
        search = OSSubmission.search(using=self.client, index=self.index)[0:10000]

        if term is not None:
            if fields is None:
                fields = self.search_fields
            search = search.query(Q("multi_match", query=term, fields=fields))

        result = search.execute()

        return result

    def get_summary(self, coordinator_id=None, include_imported=False, flatten_participants=True):
        s = OSSubmission.search(using=self.client, index=self.index)[0:10000]

        # Exclude items migrated from hepdata.cedar.ac.uk by filtering on coordinator
        # (coordinator 1 is the default user used for imports) and removing items
        # with last_updated before 2017 (e.g. where v2 has been created on HEPData.net)
        if not include_imported:
            s = s.exclude('term', coordinator=1)
            s = s.exclude('range', last_updated={'lte': AdminIndexer.EXCLUDE_BEFORE_DATE})

        if coordinator_id:
            s = s.filter('term', coordinator=coordinator_id)

        s = s.sort('last_updated')
        results = s.execute()

        processed_results = [record.as_custom_dict(exclude=[], flatten_participants=flatten_participants) for record in results.hits]
        return processed_results

    def delete_by_id(self, *args):
        """
        Deletes records from the submissions index by id
        (HEPSubmission.id)
        """
        delete_count = 0
        for id in args:
            try:
                self.client.delete(self.index, id)
                delete_count += 1
            except:
                return delete_count, False

        return delete_count, True

    def index_submission(self, submission):
        participants = []

        for sub_participant in get_submission_participants_for_record(submission.publication_recid,
                                                                      roles=['uploader', 'reviewer'],
                                                                      status='primary'):
            participants.append({
                'full_name': sub_participant.full_name,
                'role': sub_participant.role,
                'email': sub_participant.email
            })

        record_information = get_record_contents(submission.publication_recid,
                                                 submission.overall_status)

        data_count = DataSubmission.query.filter(DataSubmission.publication_recid == submission.publication_recid,
                                                 DataSubmission.version == submission.version).count()

        if record_information:
            collaboration = ','.join(record_information.get('collaborations', []))
            coordinator_request = CoordinatorRequest.query.filter_by(
                user=submission.coordinator, approved=True
            ).first()
            if coordinator_request:
                coordinator_group = coordinator_request.collaboration
            else:
                if submission.coordinator == 1:
                    coordinator_group = 'HEPData Admin'
                else:
                    coordinator_group = ''

            self.add_to_index(_id=submission.id,
                              title=record_information['title'],
                              collaboration=collaboration,
                              recid=submission.publication_recid,
                              inspire_id=submission.inspire_id,
                              arxiv_id=record_information.get('arxiv_id', None),
                              status=submission.overall_status,
                              data_count=data_count,
                              creation_date=submission.created,
                              last_updated=submission.last_updated,
                              version=submission.version,
                              participants=participants,
                              coordinator=submission.coordinator,
                              coordinator_group=coordinator_group)

    def reindex(self, *args, **kwargs):

        recreate = kwargs.get('recreate', False)
        include_imported = kwargs.get('include_imported', False)

        if recreate:
            self.recreate_index()

        submissions_query = HEPSubmission.query.filter(
            HEPSubmission.overall_status != 'sandbox',
            HEPSubmission.overall_status != 'sandbox_processing'
        )

        if not include_imported:
            submissions_query = submissions_query.filter(
                HEPSubmission.coordinator > 1,
                HEPSubmission.last_updated >= AdminIndexer.EXCLUDE_BEFORE_DATE
            )

        submissions = submissions_query.all()
        print(f'Indexing {len(submissions)} submissions...')

        for i, submission in enumerate(submissions):
            self.index_submission(submission)
            if i % 100 == 0:
                print(f"Indexed {i} of {len(submissions)}")

        print(f"Finished indexing {len(submissions)} submissions")

    def recreate_index(self):
        """ Delete and then create a given index and set a default mapping.

        :param index: [string] name of the index. If None a default is used
        """
        submission = Index(self.index)
        submission.delete(ignore=404)

        OSSubmission.init(self.index)

    def add_to_index(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        new_sub = OSSubmission(index=self.index, **kwargs)
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

        obj = OSSubmission.get(**kwargs)
        obj.delete()
