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

from flask import request, url_for


def modify_query(path, **new_values):
    """ Fetch the query arguments, update them and generate a new URL.

    :param path: [string] endpoint function name. Should contain the blueprint
           name or just a dot at the beginning for the same blueprint
    :param ``**new_values``: [string] dictionary containing parameters to update.
           When a parameter value is None, it is removed from the URL.
    :return: [string] generated URL
    """
    args = request.args.copy()

    for key, value in list(new_values.items()):
        if value is not None:
            args[key] = value
        elif key in args:
            del args[key]

    return url_for(path, **args)
