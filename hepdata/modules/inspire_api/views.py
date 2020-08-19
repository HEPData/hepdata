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

"""Choose old or new INSPIRE API."""

USE_NEW_INSPIRE_API = True

if USE_NEW_INSPIRE_API is True:
    from hepdata.modules.new_inspire_api.views import get_inspire_record_information, get_record_from_inspire, blueprint  # noqa
else:
    from hepdata.modules.old_inspire_api.views import get_inspire_record_information, get_record_from_inspire, blueprint  # noqa
