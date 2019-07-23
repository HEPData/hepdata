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
#

from flask_admin.contrib.sqla import ModelView
from .models import HEPSubmission, DataResource


def _(x):
    """Identity."""
    return x


class HEPSubmissionAdminView(ModelView):
    """HEPSubmissionAdminView view."""

    can_view_details = True
    can_delete = False

    column_list = (
        'id',
        'publication_recid',
        'overall_status',
        'coordinator',
        'doi',
        'version'
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



class DataResourceAdminView(ModelView):
    can_view_details = True
    can_delete = True

    column_list = (
        'id',
        'file_location',
        'file_type',
        'created'
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


hep_submission_admin_view = {
    'model': HEPSubmission,
    'modelview': HEPSubmissionAdminView,
    'category': _('HEPData Submissions'),
}


hep_dataresource_admin_view = {
    'model': DataResource,
    'modelview': DataResourceAdminView,
    'category': _('HEPData Submissions'),
}
