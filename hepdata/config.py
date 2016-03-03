# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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
import os
import tempfile
from datetime import timedelta


def _(x):
    return x


# Database
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+psycopg2://localhost/hepdata")
SQLALCHEMY_ECHO = False

# Default language and timezone
BABEL_DEFAULT_LANGUAGE = 'en'
BABEL_DEFAULT_TIMEZONE = 'Europe/Zurich'
I18N_LANGUAGES = [
    ('fr', _('French')),
    ('it', _('Italian'))
]

# Distributed task queue
BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_ACCEPT_CONTENT = ['json', 'msgpack', 'yaml']

# Cache
CACHE_KEY_PREFIX = "cache::"
CACHE_REDIS_URL = "redis://localhost:6379/0"
CACHE_TYPE = "redis"

# Session
SESSION_REDIS = "redis://localhost:6379/0"

# ElasticSearch
ELASTICSEARCH_HOST = "localhost"

# Accounts
RECAPTCHA_PUBLIC_KEY = "CHANGE_ME"
RECAPTCHA_SECRET_KEY = "CHANGE_ME"

SECURITY_REGISTER_USER_TEMPLATE = \
    "hepdata_theme/security/register_user.html"
SECURITY_LOGIN_USER_TEMPLATE = \
    "hepdata_theme/security/login_user.html"

SECURITY_FORGOT_PASSWORD_TEMPLATE = "hepdata_theme/security/forgot_password.html"
SECURITY_RESET_PASSWORD_TEMPLATE = "hepdata_theme/security/reset_password.html"

SECURITY_CONFIRM_SALT = "CHANGE_ME"
SECURITY_EMAIL_SENDER = "info@hepdata.net"
SECURITY_EMAIL_SUBJECT_REGISTER = _("Welcome to HEPData!")
SECURITY_LOGIN_SALT = "CHANGE_ME"
SECURITY_PASSWORD_SALT = "CHANGE_ME"
SECURITY_REMEMBER_SALT = "CHANGE_ME"
SECURITY_RESET_SALT = "CHANGE_ME"

# Theme
THEME_SITENAME = _("HEPData")
THEME_TWITTERHANDLE = "@HEPData"
THEME_LOGO = "img/hepdata_logo.svg"
THEME_GOOGLE_SITE_VERIFICATION = [
    "5fPGCLllnWrvFxH9QWI0l1TadV7byeEvfPcyK2VkS_s",
    "Rp5zp04IKW-s1IbpTOGB7Z6XY60oloZD5C3kTM-AiY4"
]

BASE_TEMPLATE = "hepdata_theme/page.html"
COVER_TEMPLATE = "hepdata_theme/page_cover.html"
SETTINGS_TEMPLATE = "invenio_theme/page_settings.html"

ELASTICSEARCH_INDEX = 'hepdata'
SEARCH_ELASTIC_HOSTS = [
    'localhost:9200'
]

SEARCH_AUTOINDEX = []

CFG_PUB_TYPE = 'publication'
CFG_DATA_TYPE = 'datatable'
CFG_ES_AUTHORS = ('authors', 'author')  # (index_name, doc_type)
CFG_DATA_KEYWORDS = ['observables', 'reactions', 'cmenergies', 'phrases']

CFG_CONVERTER_URL = 'http://hepdata-converter.cern.ch'
CFG_SUPPORTED_FORMATS = ['yaml', 'root', 'csv', 'yoda']

CFG_TMPDIR = tempfile.gettempdir()
CFG_DATADIR = tempfile.gettempdir()

MAIL_SERVER = 'mail.smtp2go.com'
MAIL_PORT = 2525
MAIL_DEFAULT_SENDER = 'submissions@hepdata.net'
SMTP_NO_PASSWORD = True
MAIL_USERNAME = 'submissions@hepdata.net'
MAIL_PASSWORD = ''

ACCOUNTS_USE_CELERY = False

# RECORDS_REST_ENDPOINTS = dict(
#     recid=dict(
#         pid_type='recid',
#         pid_minter='recid_minter',
#         pid_fetcher='recid_fetcher',
#         search_index='records',
#         search_type=None,
#         record_serializers={
#             'application/json': ('invenio_records_rest.serializers'
#                                  ':json_v1_response'),
#         },
#         search_serializers={
#             'application/json': ('invenio_records_rest.serializers'
#                                  ':json_v1_search'),
#         },
#         list_route='/records/',
#         item_route='/records/<pid_value>',
#     ), )

# DebugToolbar
DEBUG_TB_ENABLED = False
DEBUG_TB_INTERCEPT_REDIRECTS = False

# DataCite DOI minting:
# http://datacite.readthedocs.org/en/latest/

HEPDATA_DOI_PREFIX = "10.17182"
TEST_DOI_PREFIX = "10.5072"
SITE_URL = "https://www.hepdata.net"

DOI_PREFIX = TEST_DOI_PREFIX

PIDSTORE_DATACITE_USERNAME = "CERN.HEPDATA"
PIDSTORE_DATACITE_PASSWORD = ""
PIDSTORE_DATACITE_TESTMODE = False
PIDSTORE_DATACITE_URL = "https://mds.datacite.org"

# To get twitter to work, go to https://apps.twitter.com/ and create an application owned by the user account to
# which the tweets will be sent. Then, follow the instructions here to get hold of access tokens:
# https://dev.twitter.com/docs/auth/tokens-devtwittercom
# Fill these values in in the appropriate places below

# Authentication info. for Twitter here
OAUTH_TOKEN = ""
OAUTH_SECRET = ""
CONSUMER_KEY = ""
CONSUMER_SECRET = ""

USE_TWITTER = True
TWITTER_HANDLE_MAPPINGS = {
    "lhcb": "@LHCbPhysics",
    "atlas": "@ATLASpapers",
    "cms": "@CMSpapers",
    "alice": "@ALICEexperiment",
}

THEME_404_TEMPLATE = "hepdata_theme/404.html"
THEME_500_TEMPLATE = "hepdata_theme/500.html"

# Import local config file if it is present.
try:
    from hepdata.config_local import *
except ImportError:
    pass
