#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

"""HEPData utils test cases."""

from hepdata.utils.miscellanous import splitter


def test_utils():
    docs = [{'id': 1, 'type': 'publication'},
            {'related_publication': 1, 'id': 2, 'type': 'data_table'},
            {'related_publication': 1, 'id': 3, 'type': 'data_table'},
            {'related_publication': 1, 'id': 4, 'type': 'data_table'},
            {'related_publication': 1, 'id': 5, 'type': 'data_table'},
            {'related_publication': 1, 'id': 6, 'type': 'data_table'},
            {'related_publication': 1, 'id': 7, 'type': 'data_table'},
            {'related_publication': 1, 'id': 8, 'type': 'data_table'}]
    datatables, publications = splitter(docs, lambda d: 'related_publication' in d)

    assert (publications[0]['id'] == 1)
    assert (publications[0]['type'] == 'publication')
    assert (datatables[0]['type'] == 'data_table')
