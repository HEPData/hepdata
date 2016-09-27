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
#

"""Enchancers for the document sent to elastic search """
import datetime
import json
import logging

import requests
from dateutil.parser import parse
from flask import current_app

from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.api import get_latest_hepsubmission
from hepdata.utils import session

FORMATS = ['json', 'root', 'yaml', 'csv']

logging.basicConfig()
log = logging.getLogger(__name__)


def add_data_submission_urls(doc):
    doc['access_urls'] = {'links': {}}

    for format in FORMATS:
        doc['access_urls']['links'][format] = '{0}/download/submission/ins{1}/{2}/{3}'.format(
            current_app.config['SITE_URL'],
            doc['inspire_id'], doc['version'],
            format)


def add_data_table_urls(doc):
    doc['access_urls'] = {'links': {}}
    for format in FORMATS:
        doc['access_urls']['links'][format] = '{0}/download/table/ins{1}/{2}/{3}'.format(
            current_app.config['SITE_URL'],
            doc['inspire_id'], doc['title'], format)


def add_shortened_authors(doc):
    doc["summary_authors"] = []
    if doc['authors']:
        doc["summary_authors"] = doc["authors"][:10]


def add_analyses(doc):
    """
    TODO: Generalise for other badges other than rivit
    :param doc:
    :return:
    """

    # do lookup from http://rivet.hepforge.org/list_of_analyses.json
    # for HEPforge. But only one lookup.

    # look up once per day, and cache the result in REDIS.

    latest_submission = get_latest_hepsubmission(recid=doc['recid'])

    doc["analyses"] = []
    for reference in latest_submission.references:
        if reference.file_type in current_app.config['ANALYSES_ENDPOINTS']:
            doc["analyses"].append({'type': reference.file_type, 'analysis': reference.file_location})


def get_last_submission_event(recid):
    submission_participant = SubmissionParticipant.query.filter_by(
        publication_recid=recid).order_by('action_date').first()
    last_updated = None
    if submission_participant:
        last_action_date = submission_participant.action_date
        if last_action_date:
            try:
                if last_action_date <= datetime.datetime.now():
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
    add_data_table_urls(doc)


def enhance_publication_document(doc):
    add_data_submission_urls(doc)
    add_shortened_authors(doc)
    process_last_updates(doc)
    add_analyses(doc)
