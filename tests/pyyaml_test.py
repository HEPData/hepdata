# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2021 CERN.
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

import pytest
import yaml


def test_parse_trailing_tab_libyaml():
    """
    Check that PyYAML (with LibYAML) can parse a trailing tab character.
    Currently this is only possible with LibYAML, not with pure-Python PyYAML.

    :return:
    """

    data = yaml.load('key: value\t', Loader=yaml.CSafeLoader)
    assert data['key'] == 'value'


def test_parse_trailing_tab_pyyaml():
    """
    Latest PyYAML v5.4.1 (pure Python) currently has a bug parsing a trailing tab character.
    https://github.com/yaml/pyyaml/issues/306 and https://github.com/yaml/pyyaml/issues/450

    :return:
    """

    with pytest.raises(yaml.scanner.ScannerError):
        yaml.load('key: value\t', Loader=yaml.SafeLoader)
