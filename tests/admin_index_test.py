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
import logging

from elasticsearch_dsl import Index


logging.basicConfig()
log = logging.getLogger(__name__)


def test_recreate_index(admin_idx):
    admin_idx.recreate_index()

    index = Index(admin_idx.index)
    assert (index.exists())


def test_add_to_index(admin_idx):
    files = [{'_id': 1, 'recid': 1, 'title': 'Test Submission', 'collaboration': 'ATLAS', 'version': 1,
              'inspire_id': '122111',
              'status': 'finished', 'creation_date': '2016-06-01', 'last_updated': '2016-06-01'},
             {'_id': 2, 'recid': 2, 'title': 'Test Submission', 'collaboration': 'ATLAS', 'version': 1,
              'inspire_id': '122112',
              'status': 'finished', 'creation_date': '2016-06-02', 'last_updated': '2016-06-02'},
             {'_id': 3, 'recid': 3, 'title': 'Test Submission', 'collaboration': 'ALICE', 'version': 1,
              'inspire_id': '122113',
              'status': 'finished', 'creation_date': '2016-06-02', 'last_updated': '2016-06-02'}
             ]

    for file in files:
        assert (admin_idx.add_to_index(**file))


def test_search_index(admin_idx):
    all_results = admin_idx.search()
    assert (len(all_results) == 3)

    results_122111 = admin_idx.search(term='122111')
    assert (len(results_122111) == 1)

    results_atlas = admin_idx.search(term='ATLAS', fields=['collaboration'])
    assert (len(results_atlas) == 2)

    results_alice = admin_idx.search(term='ALICE', fields=['collaboration'])
    assert (len(results_alice) == 1)


def test_summary(admin_idx):
    summary = admin_idx.get_summary()
    assert (summary is not None)
    assert (len(summary) == 3)


def test_find_and_delete(admin_idx):
    delete_count, success = admin_idx.find_and_delete(term='ATLAS', fields=['collaboration'])
    assert (success)
    assert (delete_count == 2)
