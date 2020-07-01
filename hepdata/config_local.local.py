SITE_URL = "http://localhost:5000"
TESTING = True
NO_DOI_MINTING = True
USE_TWITTER = False
CFG_CONVERTER_URL = 'http://localhost:5500'
CFG_TMPDIR = '~/tmp'
CFG_DATADIR = '~/tmp'
MAIL_SERVER = 'localhost'
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
# RUN_SELENIUM_LOCALLY = True
# RATELIMIT_ENABLED = False
