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

import copy
import os
import tempfile
from celery.schedules import crontab
from datetime import timedelta

from invenio_oauthclient.contrib.orcid import REMOTE_APP as ORCID_REMOTE_APP
from invenio_oauthclient.contrib import cern


def _(x):
    return x


# Database
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+psycopg2://hepdata:hepdata@localhost/hepdata")
SQLALCHEMY_ENGINE_OPTIONS = {
    'echo': False,
    'pool_recycle': 7200
}

# Default language and timezone
BABEL_DEFAULT_LANGUAGE = 'en'
BABEL_DEFAULT_TIMEZONE = 'Europe/Zurich'
I18N_LANGUAGES = [
    ('en_gb', _('English')),
    ('fr', _('French')),
    ('it', _('Italian'))
]

# Distributed task queue
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_ACCEPT_CONTENT = ['json', 'msgpack', 'yaml']
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_CREATE_MISSING_QUEUES = True
CELERY_TASK_ROUTES = {
    'hepdata.modules.email.utils.send_email': {'queue': 'priority'},
    'hepdata.modules.records.api.process_saved_file': {'queue': 'priority'},
}

CELERY_BEAT_SCHEDULE = {
    'update_analyses': {
        'task': 'hepdata.modules.records.migrator.api.update_analyses',
        'schedule': crontab(minute=0, hour=0),  # execute daily at midnight UTC
    },
    'update_from_inspire': {
        'task': 'hepdata.modules.records.utils.records_update_utils.update_records_info_on',
        'schedule': crontab(minute=0, hour=2),  # execute daily at 2am UTC
        'args': (1,),  # INSPIRE records (with HEPData) updated yesterday
    },
}

# Cache
CACHE_KEY_PREFIX = "cache::"
CACHE_REDIS_URL = "redis://localhost:6379/0"
CACHE_TYPE = "redis"

# Session
SESSION_REDIS = "redis://localhost:6379/0"
PERMANENT_SESSION_LIFETIME = timedelta(days=1)

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
SECURITY_SEND_CONFIRMATION_TEMPLATE = "hepdata_theme/security/send_confirmation.html"

SECURITY_LOGIN_WITHOUT_CONFIRMATION = False
SECURITY_CONFIRMABLE = True
SECURITY_MSG_LOGIN = (
    "Please log in to access this page. If you signed up via ORCID or CERN you may need to confirm your email address: see the 'Resend confirmation email' link below.",
    "info")
SECURITY_MSG_CONFIRMATION_REQUIRED = (
    "Email requires confirmation. If you no longer have the confirmation email, use the 'Resend confirmation email' link below.",
    "error")
SECURITY_POST_CONFIRM_VIEW = "/dashboard/"
SECURITY_POST_REGISTER_VIEW = "/signup/"

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

ELASTICSEARCH_INDEX = 'hepdata-main'
SUBMISSION_INDEX = 'hepdata-submission'
AUTHOR_INDEX = 'hepdata-authors'
SEARCH_ELASTIC_HOSTS = [
    'localhost:9200'
]

SEARCH_AUTOINDEX = []

UPLOAD_MAX_SIZE = 52000000 # Upload limit in bytes
NGINX_TIMEOUT = 298 # Client-side timeout in s (should be slightly smaller than server timeout)

CFG_PUB_TYPE = 'publication'
CFG_DATA_TYPE = 'datatable'
CFG_SUBMISSIONS_TYPE = 'submission'
CFG_DATA_KEYWORDS = ['observables', 'reactions', 'cmenergies', 'phrases']

CFG_CONVERTER_URL = 'https://converter.hepdata.net'
CFG_SUPPORTED_FORMATS = ['yaml', 'root', 'csv', 'yoda']
CFG_CONVERTER_TIMEOUT = NGINX_TIMEOUT # timeout in seconds

CFG_TMPDIR = tempfile.gettempdir()
CFG_DATADIR = tempfile.gettempdir()

MAIL_SERVER = 'cernmx.cern.ch'
MAIL_PORT = ''
MAIL_DEFAULT_SENDER = 'submissions@hepdata.net'
SMTP_NO_PASSWORD = True
SMTP_ENCRYPTION = False
MAIL_USERNAME = ''
MAIL_PASSWORD = ''

if MAIL_PASSWORD is '':
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

ACCOUNTS_USE_CELERY = False

RECORDS_REST_ENDPOINTS = dict(
    recid=dict(
        pid_type='recid',
        pid_minter='recid_minter',
        pid_fetcher='recid_fetcher',
        search_index='records',
        search_type=None,
        record_serializers={
            'application/json': ('invenio_records_rest.serializers'
                                 ':json_v1_response'),
        },
        search_serializers={
            'application/json': ('invenio_records_rest.serializers'
                                 ':json_v1_search'),
        },
        list_route='/records/',
        item_route='/records/<pid_value>',
    ), )

# DebugToolbar
DEBUG_TB_ENABLED = False
DEBUG_TB_INTERCEPT_REDIRECTS = False

# DataCite DOI minting:
# http://datacite.readthedocs.org/en/latest/

HEPDATA_DOI_PREFIX = "10.17182"
TEST_DOI_PREFIX = "10.5072"
SITE_URL = "https://www.hepdata.net"

DOI_PREFIX = HEPDATA_DOI_PREFIX

PIDSTORE_DATACITE_USERNAME = "CERN.HEPDATA"
PIDSTORE_DATACITE_PASSWORD = ""
PIDSTORE_DATACITE_TESTMODE = False
PIDSTORE_DATACITE_URL = "https://mds.datacite.org"

TESTING = False  # switch off email using TESTING = True
NO_DOI_MINTING = False  # switch off DOI minting using NO_DOI_MINTING = True

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
    "atlas": "@AtlasPapers",
    "cms": "@CMSpapers",
    "alice": "@AlicePapers",
    "t2k": "@Tokai2Kamioka",
    "phenix": "@RHIC_PHENIX",
    "star": "@RHIC_STAR",
    "minerva": "@minervaexpt",
    "bicep2": "@BICEPTWO",
    "xenon": "@Xenon1T",
}

INVALID_DOI_TEMPLATE = "hepdata_theme/invalid_doi.html"
THEME_403_TEMPLATE = "hepdata_theme/403.html"
THEME_404_TEMPLATE = "hepdata_theme/404.html"
THEME_500_TEMPLATE = "hepdata_theme/500.html"

#: Change default template for oauth sign up.
OAUTHCLIENT_SIGNUP_TEMPLATE = 'hepdata_theme/security/oauth_register_user.html'
#: Stop oauthclient from taking over template.
OAUTHCLIENT_TEMPLATE_KEY = None

#: Credentials for ORCID (must be changed to work).
ORCID_APP_CREDENTIALS = dict(
    consumer_key="CHANGE_ME",
    consumer_secret="CHANGE_ME",
)

CERN_APP_CREDENTIALS = dict(
    consumer_key="CHANGE_ME",
    consumer_secret="CHANGE_ME",
)

CERN_REMOTE_APP = copy.deepcopy(cern.REMOTE_APP)
CERN_REMOTE_APP["params"].update({
    'request_token_params': {
        "scope": "Email Groups",
    }
})

#: Definition of OAuth client applications.
OAUTHCLIENT_REMOTE_APPS = dict(
    orcid=ORCID_REMOTE_APP,
    cern=CERN_REMOTE_APP
)

ADMIN_APPNAME = "HEPData"

# These values are converted to strings
SPECIAL_VALUES = ['inf', '+inf', '-inf', 'nan']

# ANALYSES_ENDPOINTS
ANALYSES_ENDPOINTS = {
    'rivet': {
        'endpoint_url': 'http://rivet.hepforge.org/analyses.json',
        'url_template': 'http://rivet.hepforge.org/analyses/{0}'
    },
    #'ufo': {},
    #'xfitter': {},
    #'applgrid': {},
    #'fastnlo': {},
    #'madanalysis': {},
}

ADMIN_EMAIL = 'info@hepdata.net'
SUBMISSION_FILE_NAME_PATTERN = 'HEPData-{}-v{}-yaml.zip'

# For ignoring URLLIB3 errors on the server where we use https for elastic search,
# but the certificate is generated on our side.
PYTHONWARNINGS="ignore:Unverified HTTPS request"

PRODUCTION_MODE = False

RUN_SELENIUM_LOCALLY = False

# This is needed for invenio-oauthclient==1.1.3.
# Default value of None gives an exception.
# It can be removed for invenio-oauthclient>=1.3.0.
APP_ALLOWED_HOSTS = []

LOGGING_SENTRY_CELERY = True  # for invenio-logging

# HTML attributes and tags allowed in record descriptions
# If these are modified, update tips.rst in hepdata-submission
ALLOWED_HTML_ATTRS = {'a': ['href', 'title', 'name', 'rel'], 'abbr': ['title'], 'acronym': ['title']}
ALLOWED_HTML_TAGS = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'i', 'li', 'ol', 'p', 'pre', 'span', 'strike', 'strong', 'sub', 'sup', 'u', 'ul']

# Talisman settings (see https://github.com/GoogleCloudPlatform/flask-talisman).
# We don't want the web pods to use https.
APP_DEFAULT_SECURE_HEADERS = {
    'force_https': False,
    'force_https_permanent': False,
    'force_file_save': False,
    'frame_options': 'sameorigin',
    'frame_options_allow_from': None,
    'strict_transport_security': False,
    'strict_transport_security_preload': False,
    'strict_transport_security_max_age': 31556926,  # One year in seconds
    'strict_transport_security_include_subdomains': True,
    'content_security_policy': {},
    'content_security_policy_report_uri': None,
    'content_security_policy_report_only': False,
    'session_cookie_secure': False,
    'session_cookie_http_only': False
}

# Import local config file if it is present.
try:
    from hepdata.config_local import *
except ImportError:
    pass
