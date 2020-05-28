FROM inspirehep/python:2.7

WORKDIR /code

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
 pip install --no-cache-dir --upgrade setuptools && \
 pip install --no-cache-dir --upgrade wheel && \
 pip install -e . -r requirements.txt --pre

WORKDIR  /usr/var/hepdata-instance/static

RUN hepdata npm \
 && npm install \
 && hepdata collect -v \
 && hepdata assets build

ARG APP_ENVIRONMENT
RUN bash -c "set -x; echo $APP_ENVIRONMENT; [[ ${APP_ENVIRONMENT:-prod} = local ]] && (cd /usr/var && wget https://saucelabs.com/downloads/sc-4.5.4-linux.tar.gz && \
  tar -xvf sc-4.5.4-linux.tar.gz) || echo 'Not installing SC on prod build'"

WORKDIR /code
