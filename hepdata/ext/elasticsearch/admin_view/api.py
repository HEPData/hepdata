import logging

from elasticsearch import Elasticsearch
from elasticsearch_dsl import DocType, String, Date, Integer, Nested, InnerObjectWrapper, Q, Index, Search
from elasticsearch_dsl.connections import connections
from flask import current_app

from hepdata.modules.records.utils.common import get_record_by_id, get_record_contents
from hepdata.modules.submission.models import HEPSubmission, DataSubmission

logging.basicConfig()
log = logging.getLogger(__name__)


class ESSubmissionParticipant(InnerObjectWrapper):
    pass


class ESSubmission(DocType):
    recid = Integer()
    inspire_id = String()
    version = Integer()
    title = String()
    collaboration = String()
    status = String()
    creation_date = Date()
    last_updated = Date()
    data_count = Integer()
    participants = Nested(
        doc_class=ESSubmissionParticipant,
        properties={
            'role': String(fields={'raw': String(index='not_analyzed')}),
            'full_name': String()
        }
    )

    def as_custom_dict(self, exclude=None):
        _dict_ = vars(self)

        data = _dict_['_d_']
        data['creation_date'] = data['creation_date'].strftime('%Y-%m-%d')
        data['last_updated'] = data['last_updated'].strftime('%Y-%m-%d')

        participants = data['participants']
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
        s.aggs.bucket('daily_workflows', 'date_histogram',
                      field='last_updated',
                      format="yyyy-MM-dd", interval='day') \
            .bucket('inspire_ids', 'terms', field='inspire_id')
        result = s.execute().aggregations.to_dict()

        # flatten summary
        processed_result = []
        _daily_workflows = result['daily_workflows']
        for day in _daily_workflows['buckets']:
            for inspire_id in day['inspire_ids']['buckets']:
                record_search = self.search(term=inspire_id['key'], fields=['inspire_id'])
                record = record_search[0] if len(record_search) == 1 else record_search[1]

                processed_result.append(record.as_custom_dict(exclude=[]))

        return processed_result

    def reindex(self, *args, **kwargs):

        recreate = kwargs.get('recreate', False)
        if recreate:
            self.recreate_index()

        submissions = HEPSubmission.query.all()

        for submission in submissions:
            participants = []

            for sub_participant in submission.participants:
                participants.append({'full_name': sub_participant.full_name, 'role': sub_participant.role})

            record_information = get_record_contents(submission.publication_recid)

            data_count = DataSubmission.query.filter(DataSubmission.publication_recid == submission.publication_recid,
                                                     DataSubmission.version == submission.version).count()

            collaboration = ','.join(record_information['collaborations'])

            self.add_to_index(_id=submission.id,
                              title=record_information['title'],
                              collaboration=collaboration,
                              recid=submission.publication_recid,
                              inspire_id=submission.inspire_id,
                              status=submission.overall_status,
                              data_count=data_count,
                              creation_date=submission.created,
                              last_updated=submission.last_updated,
                              version=submission.version,
                              participants=participants)

    def recreate_index(self):
        """ Delete and then create a given index and set a default mapping.

        :param index: [string] name of the index. If None a default is used
        """
        submission = Index(self.index)
        submission.delete(ignore=404)

        ESSubmission.init()

    def add_to_index(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return:
        """
        new_sub = ESSubmission(**kwargs)
        return new_sub.save()

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
