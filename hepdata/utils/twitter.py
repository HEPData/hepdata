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

"""Twitter API."""

from hepdata.modules.records.utils.common import encode_string, decode_string, truncate_string
from pytwitter import Api
from pytwitter.error import PyTwitterError
from hepdata.config import USE_TWITTER, TWITTER_HANDLE_MAPPINGS
from flask import current_app
from unicodeit import replace
from mathml_to_latex.converter import MathMLToLaTeX
import re


def tweet(title, collaborations, url, version=1):
    """
    Announce addition or revision of a HEPData record on Twitter.

    :param title:
    :param collaborations:
    :param url:
    :param version:
    :return:
    """
    if USE_TWITTER:

        OAUTH_TOKEN = current_app.config['OAUTH_TOKEN']
        OAUTH_SECRET = current_app.config['OAUTH_SECRET']
        CONSUMER_KEY = current_app.config['CONSUMER_KEY']
        CONSUMER_SECRET = current_app.config['CONSUMER_SECRET']

        if not OAUTH_TOKEN or not OAUTH_SECRET or not CONSUMER_KEY or not CONSUMER_SECRET:
            # log this error
            print("Twitter credentials must be supplied!")
        else:
            api = Api(
                consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
                access_token=OAUTH_TOKEN, access_secret=OAUTH_SECRET
            )

            cleaned_title = decode_string(encode_string(title))  # in case of binary characters in title

            # Replace MathML expressions with LaTeX expressions.
            # Use negative lookahead in regex to match innermost <math>.*</math>.
            cleaned_title = re.sub(r'(<math>((?!<math>).)*</math>)',
                                   lambda m: MathMLToLaTeX().convert(m.group()), cleaned_title)

            cleaned_title = replace(cleaned_title)  # use UnicodeIt to replace LaTeX expressions
            cleaned_title = cleanup_latex(cleaned_title)  # remove some remaining LaTeX encodings

            words = len(cleaned_title.split())

            # Try to tweet with complete paper title.
            # If tweet exceeds 280 characters, keep trying with one less word each time.
            tweeted = False
            while words and not tweeted:

                try:

                    if version == 1:
                        status = "Added{0} data on \"{1}\" to {2}".format(
                            get_collaboration_string(collaborations),
                            truncate_string(cleaned_title, words), url)
                    else:
                        status = "Revised{0} data on \"{1}\" at {2}?version={3}".format(
                            get_collaboration_string(collaborations),
                            truncate_string(cleaned_title, words), url, version)

                    api.create_tweet(text=status)
                    tweeted = True
                    print("Tweeted: {}".format(status))

                except PyTwitterError as e:
                    message = e.message
                    if 'errors' in message and message['errors'][0]['message'].startswith(
                        "Your Tweet text is too long."):
                        words = words - 1  # Try again with one less word.
                    else:
                        print(message)
                        break

            if not tweeted:
                print("Failed to post tweet for record {0}".format(url))


def cleanup_latex(latex_string):
    """Replace some spurious LaTeX encoding characters and expressions."""

    chars_to_replace = ["$", "{", "}"]
    for char_to_replace in chars_to_replace:
        latex_string = latex_string.replace(char_to_replace, "")

    latex_string = latex_string.replace("~", " ")

    exprs_to_replace = [r"\\mathrm\s*", r"\\text\s*", r"\\rm\s*"]
    for expr_to_replace in exprs_to_replace:
        latex_string = re.sub(expr_to_replace, "", latex_string)

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
