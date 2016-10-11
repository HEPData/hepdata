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


from __future__ import absolute_import, print_function

from hepdata.modules.records.utils.common import encode_string, truncate_string
from twitter import Twitter
from twitter import OAuth
from hepdata.config import OAUTH_TOKEN, OAUTH_SECRET, CONSUMER_KEY, CONSUMER_SECRET, USE_TWITTER, \
    TWITTER_HANDLE_MAPPINGS


def tweet(title, collaborations, url):
    """
    :param title:
    :param collaborations:
    :param url:
    :return:
    """
    if USE_TWITTER:
        if not OAUTH_TOKEN or not OAUTH_SECRET or not CONSUMER_KEY or not CONSUMER_SECRET:
            # log this error
            print("Twitter credentials must be supplied!")
        else:
            twitter = Twitter(auth=OAuth(OAUTH_TOKEN, OAUTH_SECRET, CONSUMER_KEY, CONSUMER_SECRET))
            try:
                status = "Added{0} data on \"{1}\" to {2}".format(
                    get_collaboration_string(collaborations), truncate_string(encode_string(cleanup_latex(title)), 10),
                    url)

                twitter.statuses.update(status=status)
            except Exception as e:
                print(e.__str__())
                # It would be nice to get a stack trace here
                print("(P) Failed to post tweet for record {0}".format(url))


def cleanup_latex(latex_string):
    chars_to_replace = ["$", "{", "}"]
    for char_to_replace in chars_to_replace:
        latex_string = latex_string.replace(char_to_replace, "")

    return latex_string


def get_collaboration_string(collaborations):
    __to_return = ""
    if collaborations:
        for collaboration in collaborations:
            if collaboration.lower() in TWITTER_HANDLE_MAPPINGS:
                __to_return += " {0}".format(TWITTER_HANDLE_MAPPINGS[collaboration.lower()])
            else:
                __to_return += " #{0}".format(collaboration)

    return __to_return
