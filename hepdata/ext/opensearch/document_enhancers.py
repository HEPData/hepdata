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

"""Enhancers for the document sent to opensearch """
import os
import re
import datetime
import logging
from collections import defaultdict
from dateutil.parser import parse
from flask import current_app

from hepdata.config import CFG_PUB_TYPE, CFG_DATA_TYPE, HISTFACTORY_FILE_TYPE, NUISANCE_FILE_TYPE
from hepdata.ext.opensearch.config.record_mapping import mapping as os_mapping
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.modules.submission.models import DataSubmission
from hepdata.utils.miscellaneous import get_resource_data

FORMATS = ['json', 'root', 'yaml', 'csv', 'yoda']

logging.basicConfig()
log = logging.getLogger(__name__)


def add_id(doc):
    doc['id'] = doc['recid']


def add_doc_type(doc, doc_type):
    doc['doc_type'] = doc_type


def add_data_submission_urls(doc):
    doc['access_urls'] = {'links': {}}

    for format in FORMATS:
        doc['access_urls']['links'][format] = '{0}/download/submission/ins{1}/{2}/{3}'.format(
            current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
            doc['inspire_id'], doc['version'] if 'version' in doc else 1,
            format)


def add_data_table_urls(doc):
    doc['access_urls'] = {'links': {}}
    for format in FORMATS:

        _cleaned_table_name = doc['title'].replace('%', '%25').replace('\\', '%5C')

        doc['access_urls']['links'][format] = '{0}/download/table/ins{1}/{2}/{3}'.format(
            current_app.config.get('SITE_URL', 'https://www.hepdata.net'),
            doc['inspire_id'], _cleaned_table_name, format)


def add_parent_publication(doc):
    doc["parent_child_join"] = {
        "name": "child_datatable",
        "parent": str(doc['related_publication'])
    }


def add_parent_child_info(doc):
    doc["parent_child_join"] = {
        "name": "parent_publication"
    }


def add_shortened_authors(doc):
    doc["summary_authors"] = []
    if doc['authors']:
        doc["summary_authors"] = doc["authors"][:10]
        doc["first_author"] = doc["authors"][0]


def add_analyses(doc):
    """
    Add analyses links such as Rivet, MadAnalysis 5, SModelS, CheckMATE, HackAnalysis, Combine, HistFactory and NUISANCE to the index.

    :param doc:
    :return:
    """
    latest_submission = get_latest_hepsubmission(publication_recid=doc['recid'], overall_status='finished')

    if latest_submission:
        doc["analyses"] = []
        for reference in latest_submission.resources:
            if reference.file_type in current_app.config['ANALYSES_ENDPOINTS']:
                doc["analyses"].append({'type': reference.file_type, 'analysis': reference.file_location})
            else:
                site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
                landing_page_url = f"{site_url}/record/resource/{reference.id}?landing_page=true"
                if reference.file_type == HISTFACTORY_FILE_TYPE:
                    doc["analyses"].append({'type': reference.file_type, 'analysis': landing_page_url,
                                            'filename': os.path.basename(reference.file_location)})
                elif reference.file_type == NUISANCE_FILE_TYPE:
                    doc["analyses"].append({'type': 'NUISANCE', 'analysis': landing_page_url,
                                            'filename': os.path.basename(reference.file_location)})


def add_data_keywords(doc):
    # Aggregate and filter out invalid keywords
    valid_keywords = list(os_mapping['data_keywords']['properties'].keys())
    agg_keywords = defaultdict(list)
    for kw in doc["keywords"]:
        if kw['name'] in valid_keywords:
            agg_keywords[kw['name']].append(kw['value'])

    # Remove duplicates
    for k, v in agg_keywords.items():
        agg_keywords[k] = list(set(v))

    agg_keywords = process_cmenergies(agg_keywords)
    doc['data_keywords'] = dict(agg_keywords)


def add_data_abstract(doc):
    """
    Adds the data abstract from its associated HEPSubmission to the document object

    :param doc: The document object
    :return:
    """

    submission = get_latest_hepsubmission(publication_recid=doc['recid'], overall_status='finished')
    doc['data_abstract'] = submission.data_abstract


def add_data_resources(doc):
    """
    Triggers resource data generation of a DataSubmission object.
    Gets the DataSubmission object, then passes it off for data retrival.

    :param doc: The document object
    :return:
    """

    submission = DataSubmission.query.filter_by(doi=doc["doi"]).order_by(DataSubmission.id.desc()).first()
    doc['resources'] = get_resource_data(submission)


def add_submission_resources(doc):
    """
    Triggers resource data generation of a HEPSubmission object.
    Gets the HEPSubmission object, then passes it off for data retrival.

    :param doc: The document object
    :return:
    """

    submission = get_latest_hepsubmission(publication_recid=doc['recid'], overall_status='finished')
    doc['resources'] = get_resource_data(submission)


def process_cmenergies(keywords):
    cmenergies = []
    if keywords['cmenergies']:
        for cmenergy in keywords['cmenergies']:
            cmenergy = cmenergy.strip(" gevGEV")
            try:
                cmenergy_val = float(cmenergy)
                cmenergies.append({"gte": cmenergy_val, "lte": cmenergy_val})
            except ValueError:
                m = re.match(r'^(-?\d+(?:\.\d+)?)[ \-+andAND]+(-?\d+(?:\.\d+)?)$', cmenergy)
                if m:
                    cmenergy_range = [float(m.group(1)), float(m.group(2))]
                    cmenergy_range.sort()
                    cmenergies.append({"gte": cmenergy_range[0], "lte": cmenergy_range[1]})
                else:
                    log.warning("Invalid value for cmenergies: %s" % cmenergy)

        keywords['cmenergies'] = cmenergies

    return keywords


def get_last_submission_event(recid):
    submission_participant = SubmissionParticipant.query.filter_by(
        publication_recid=recid).order_by('action_date').first()
    last_updated = None
    if submission_participant:
        last_action_date = submission_participant.action_date
        if last_action_date:
            try:
                if last_action_date <= datetime.datetime.utcnow():
                    last_updated = last_action_date.strftime("%Y-%m-%d")
            except ValueError as ve:
                print(ve.args)
    return last_updated


def process_last_updates(doc):
    if "last_updated" not in doc:
        last_updated = get_last_submission_event(doc["recid"])
        if not last_updated:
            last_updated = doc["creation_date"]

        doc["last_updated"] = last_updated

    if doc["year"] is not None:
        doc["publication_date"] = parse(str(doc["year"]))


def enhance_data_document(doc):
    add_id(doc)
    add_doc_type(doc, CFG_DATA_TYPE)
    add_data_table_urls(doc)
    add_parent_publication(doc)
    add_data_keywords(doc)
    add_data_resources(doc)


def enhance_publication_document(doc):
    add_id(doc)
    add_doc_type(doc, CFG_PUB_TYPE)
    add_data_submission_urls(doc)
    add_data_abstract(doc)
    add_shortened_authors(doc)
    process_last_updates(doc)
    add_analyses(doc)
    add_parent_child_info(doc)
    add_submission_resources(doc)
