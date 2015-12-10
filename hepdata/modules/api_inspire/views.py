# -*- coding: utf-8 -*-
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
#

import requests
from bs4 import BeautifulSoup
from flask import request, Blueprint, redirect, jsonify

from marcxml_parser import get_doi, get_title, get_authors, get_abstract, \
    get_arxiv, get_collaborations, get_keywords, get_date, get_journal_info

blueprint = Blueprint('inspire_datasource',
                      __name__,
                      url_prefix='/inspire',
                      template_folder='templates',
                      static_folder='static')


def get_inspire_record_information(inspire_rec_id):
    url = 'http://inspirehep.net/record/{0}/export/xm'.format(inspire_rec_id)
    req = requests.get(url)
    content = req.content
    status = req.status_code
    if status == 200:
        soup = BeautifulSoup(content, "lxml")

        content = {
            'title': [get_title(soup)],
            'doi': get_doi(soup),
            'authors': get_authors(soup),
            'abstract': get_abstract(soup),
            'creation_date': get_date(soup),
            'arxiv_id': get_arxiv(soup),
            'collaborations': get_collaborations(soup),
            'keywords': get_keywords(soup),
            'journal_info': get_journal_info(soup),
        }
        status = 'success'
    return content, status


@blueprint.route('/search')
def get_record_from_inspire():
    if 'id' not in request.args:
        return redirect('/')

    rec_id = request.args['id']

    content, status = get_inspire_record_information(rec_id)

    return jsonify({'source': 'inspire',
                    'query': content,
                    'status': status})
