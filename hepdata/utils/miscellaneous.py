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

import bleach
import html

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
    from flask import current_app

    # The lines below were copied from invenio-formatter but with the addition
    # of the strip parameter.
    value = value.strip()
    cleaned = bleach.clean(
        value,
        tags=tags or current_app.config.get('ALLOWED_HTML_TAGS', []),
        attributes=attributes or current_app.config.get(
            'ALLOWED_HTML_ATTRS', {}),
        strip=strip
    )

    # If bleach.clean returns a shorter string than the original input,
    # it must have cut off some 'invalid' HTML (rather than expanded any
    # disallowed tags). This is unlikely to be intended behaviour so it's
    # more likely that there are some < or > signs in there without spaces,
    # and that we should not treat the fragment as HTML.
    # Only do this step if using the default arguments, otherwise we might
    # expect tags/attributes to be stripped and the resulting string to be
    # shorter
    if not strip and tags is None and attributes is None \
            and len(cleaned) < len(value):
        return html.escape(value, quote=True)
    else:
        return cleaned
