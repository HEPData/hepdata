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

from celery import current_app as celery_app


def count_tasks_with_status(status, task_name=None):
    inspector = celery_app.control.inspect()

    if status == 'active':
        tasks = inspector.active()
    elif status == 'reserved':
        tasks = inspector.reserved()
    elif status == 'scheduled':
        tasks = inspector.reserved()
    else:
        raise ValueError(f"Unknown celery task status {status}")

    count = 0

    for worker, task_list in tasks.items():
        for task in task_list:
            if task_name is None or task_name == task['name']:
                count += 1
    return count
