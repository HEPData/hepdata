FROM inspirehep/python:3.6

ARG APP_ENVIRONMENT

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get update
RUN apt-get install -y nodejs

RUN npm install -g \
    clean-css@^3.4.24 \
    requirejs \
    uglify-js

RUN npm install -g --unsafe-perm \
    node-sass@4.14.1

WORKDIR /code

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
 pip install --no-cache-dir --upgrade setuptools && \
 pip install --no-cache-dir --upgrade wheel && \
 pip install -e . -r requirements.txt

RUN bash -c "set -x; [[ ${APP_ENVIRONMENT:-prod} = local-web ]] && \
  pip install -e .[all] || echo 'Not installing test or doc requirements on prod or worker build'"

WORKDIR /usr/local/var/hepdata-instance/static

RUN hepdata npm \
 && npm install \
 && hepdata collect -v \
 && hepdata assets build

RUN bash -c "echo $APP_ENVIRONMENT"

RUN bash -c "set -x; [[ ${APP_ENVIRONMENT:-prod} = local-web ]] && (cd /usr/local/var && wget https://saucelabs.com/downloads/sc-4.6.2-linux.tar.gz && \
  tar -xvf sc-4.6.2-linux.tar.gz) || echo 'Not installing SC on prod or worker build'"

WORKDIR /code

ENTRYPOINT []
