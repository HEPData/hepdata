web: hepdata --debug run
cache: redis-server
worker: celery worker -E -A hepdata.celery --loglevel=INFO --workdir="${VIRTUAL_ENV}" --autoreload --pidfile="${VIRTUAL_ENV}/worker.pid" --purge
workermon: flower --broker=amqp://guest:guest@localhost:5672
indexer: elasticsearch -Dcluster.name="hepdata" -Ddiscovery.zen.ping.multicast.enabled=false -Dpath.data="$VIRTUAL_ENV/var/data/elasticsearch"  -Dpath.logs="$VIRTUAL_ENV/var/log/elasticsearch"
