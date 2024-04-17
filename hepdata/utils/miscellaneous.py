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

import re

import bleach
from flask import current_app


def splitter(data, predicate):
    """Split a list according to a given predicate (lambda)."""
    yes, no = [], []
    for d in data:
        (yes if predicate(d) else no).append(d)
    return yes, no


def sanitize_html(value, tags=None, attributes=None, strip=False):
    """Sanitize HTML.

    :param tags: Allowed HTML ``tags``. Configuration set by Invenio-Config.
    :param attributes: Allowed HTML ``attributes``. Configuration set by
        Invenio-Config.
    :param strip: Whether to strip tags that are not allowed. Defaults to
        False (escapes rather than strips disallowed tags).

    Use this function when you need to include unescaped HTML that contains
    user provided data.
    """
    if value is None:
        return value

    from flask import current_app

    value = value.strip()

    # Look for conditions like v1<x<v2 which look like invalid HTML,
    # and escape them before running bleach
    p = re.compile('<([^>]*?)<')
    escaped = p.sub(r'&lt;\1&lt;', value)

    tags = tags if tags is not None \
        else current_app.config.get('ALLOWED_HTML_TAGS', {})
    attributes = attributes if attributes is not None \
        else current_app.config.get('ALLOWED_HTML_ATTRS', {})

    cleaned = bleach.clean(
        escaped,
        tags=tags,
        attributes=attributes,
        strip=strip
    )

    return cleaned

def generate_resource_url(resource):
    """
    Uses the file_location/ID of a submission object to generate a resource url.
    If "http" is at the beginning, will return file_location
    Otherwise, will generate a HEPData resource URL

    :param resource: DataResource object for generation
    :return: The generated URL string
    """
    # Determine if file_location is url or not
    if resource.file_location.startswith("http"):
        # Set url value if it's an external location
        url_string = resource.file_location
    else:
        # If not url, create hepdata.net url using resource ID
        site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
        url_string = f"{site_url}/record/resource/{resource.id}?landing_page=true"

    return url_string


def get_resource_data(submission):
    """
    Function to create a dictionary of description, type and url for resources objects.
    This dictionary is to be added to the OpenSearch index.
    Uses either a DataSubmission, or HEPSubmission, which both contain resource objects.

    :param submission: HEPSubmission/DataSubmission object
    :return: The resources list (of dictionaries)
    """
    resources = []

    # Create a dictionary entry for every resource
    for s in submission.resources:
        resource_data = {
            "description": s.file_description,
            "type": s.file_type,
            "url": generate_resource_url(s)
        }

        resources.append(resource_data)

    return resources
