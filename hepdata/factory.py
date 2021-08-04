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

"""HEPData application factories."""

import os
import sys

from invenio_base.app import create_app_factory
from invenio_base.wsgi import create_wsgi_factory
from invenio_config import create_config_loader

from . import config

env_prefix = 'APP'

conf_loader = create_config_loader(config=config, env_prefix=env_prefix)

instance_path = os.getenv(env_prefix + '_INSTANCE_PATH') or \
    os.path.join(sys.prefix, 'var', 'hepdata-instance')

static_folder = os.getenv(env_prefix + '_STATIC_FOLDER') or \
    os.path.join(instance_path, 'static')


create_api = create_app_factory(
    'hepdata',
    config_loader=conf_loader,
    extension_entry_points=['invenio_base.api_apps'],
    blueprint_entry_points=['invenio_base.api_blueprints'],
    instance_path=instance_path,
)


create_app = create_app_factory(
    'hepdata',
    config_loader=conf_loader,
    extension_entry_points=['invenio_base.apps'],
    blueprint_entry_points=['invenio_base.blueprints'],
    wsgi_factory=create_wsgi_factory({'/api': create_api}),
    instance_path=instance_path,
    static_folder=static_folder,
)
