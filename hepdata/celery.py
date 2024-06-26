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

"""HEPData celery application object."""
import logging
import os

from celery import shared_task
from flask_celeryext import create_celery_app

from .factory import create_app

from .config import LOGGING_SENTRY_CELERY

logging.basicConfig()
log = logging.getLogger(__name__)

celery = create_celery_app(create_app(LOGGING_SENTRY_CELERY=LOGGING_SENTRY_CELERY))

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'fixes')
def _absolutepath(filename):
    """ Return the absolute path to the filename"""
    return os.path.join(PLUGIN_FOLDER, filename)

@shared_task
def dynamic_tasks(funcname, module_name, *args, **kwargs):
    """Task to allow functions to be called dynamically from ../fixes directory"""
    try:
        fixes_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'fixes')
        filename = os.path.join(fixes_path, module_name + '.py')

        ns = {}
        with open(os.path.join(filename)) as f:
            code = compile(f.read(), filename, 'exec')
            eval(code, ns, ns)
            log.info(f"Executing function {funcname} from module {module_name}")
            return ns[funcname](*args, **kwargs)
    except IOError:
        log.error(f"Error loading dynamic function {funcname} from module {module_name}")
