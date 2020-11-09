SITE_URL = "http://localhost:5000"
TESTING = True
NO_DOI_MINTING = True
USE_TWITTER = False
CELERY_BROKER_URL = "redis://cache:6379/0"
CELERY_RESULT_BACKEND = "redis://cache:6379/1"
CACHE_REDIS_URL = "redis://cache:6379/0"
SESSION_REDIS = "redis://cache:6379/0"
TEST_DB_HOST = "postgres"
ELASTICSEARCH_HOST = "elasticsearch"
SEARCH_ELASTIC_HOSTS = [
    'elasticsearch:9200'
]
