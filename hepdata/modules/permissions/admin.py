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


from hepdata.modules.permissions.models import SubmissionParticipant, CoordinatorRequest
from flask_admin.contrib.sqla import ModelView

def _(x):
    """Identity."""
    return x


class SubmissionParticipantAdminView(ModelView):
    can_view_details = True
    can_delete = False

    column_list = (
        'publication_recid',
        'full_name',
        'email',
        'affiliation',
        'role',
        'status'
    )

    form_columns = \
        column_searchable_list = \
        column_filters = \
        column_details_list = \
        columns_sortable_list = \
        column_list

    column_labels = {
        '_displayname': _('Display Name'),
    }


class CoordinatorRequestView(ModelView):
    can_view_details = True
    can_delete = False

    column_list = (
        'collaboration',
        'approved',
        'in_queue'
    )

    form_columns = \
        column_searchable_list = \
        column_filters = \
        column_details_list = \
        columns_sortable_list = \
        column_list

    column_labels = {
        '_displayname': _('Display Name'),
    }


hep_participant_admin_view = {
    'model': SubmissionParticipant,
    'modelview': SubmissionParticipantAdminView,
    'category': _('HEPData Submissions'),
}


coordinator_request_admin_view = {
    'model': CoordinatorRequest,
    'modelview': CoordinatorRequestView,
    'category': _('Coordinator Requests'),
}
