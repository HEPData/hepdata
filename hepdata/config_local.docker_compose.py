SITE_URL = "http://localhost:5000"
TESTING = True
NO_DOI_MINTING = True
USE_TWITTER = False
CFG_CONVERTER_URL = 'http://converter:5000'
CFG_TMPDIR = '/code/tmp'
CFG_DATADIR = '/code/tmp'
MAIL_SERVER = 'localhost'
CELERY_BROKER_URL = "redis://cache:6379/0"
CELERY_RESULT_BACKEND = "redis://cache:6379/1"
CACHE_REDIS_URL = "redis://cache:6379/0"
SESSION_REDIS = "redis://cache:6379/0"
TEST_DB_HOST = "db"
ELASTICSEARCH_HOST = "es"
SEARCH_ELASTIC_HOSTS = [
    'es:9200'
]
# RUN_SELENIUM_LOCALLY = True
