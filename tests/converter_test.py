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
from hepdata.config import CFG_CONVERTER_URL
from hepdata.modules.converter.tasks import convert_and_store
import responses


def test_convert_and_store_invalid(app, capsys):
    with app.app_context():
        convert_and_store('12345678', 'test_format', True)
        captured = capsys.readouterr()
        assert(captured.out == "Unable to find a matching submission for 12345678\n")


@responses.activate
def test_convert_and_store_valid(app, capsys, load_submission):
    with app.app_context():
        responses.add(responses.GET, CFG_CONVERTER_URL + '/convert',
                      status=200, headers={'mimetype': 'application/x-gzip'})

        capsys.readouterr()
        convert_and_store('1487726', 'yaml', True)
        captured_lines = capsys.readouterr().out.splitlines()

        assert(captured_lines[0] == "Creating yaml conversion for ins1487726")
        assert(captured_lines[1].startswith("File for ins1487726 created successfully"))
