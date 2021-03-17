FROM inspirehep/python:3.6

ARG APP_ENVIRONMENT

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get update
RUN apt-get install -y nodejs

WORKDIR /code

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
 pip install --no-cache-dir --upgrade setuptools && \
 pip install --no-cache-dir --upgrade wheel && \
 pip install -e . -r requirements.txt

RUN bash -c "set -x; [[ ${APP_ENVIRONMENT:-prod} = local-web ]] && \
  pip install -e .[all] || echo 'Not installing test or doc requirements on prod or worker build'"

RUN hepdata collect -v  && \
  hepdata webpack create && \
  # --unsafe needed because we are running as root
  hepdata webpack install --unsafe && \
  hepdata webpack build


RUN bash -c "echo $APP_ENVIRONMENT"

RUN bash -c "set -x; [[ ${APP_ENVIRONMENT:-prod} = local-web ]] && (cd /usr/local/var && wget https://saucelabs.com/downloads/sc-4.6.2-linux.tar.gz && \
  tar -xvf sc-4.6.2-linux.tar.gz) || echo 'Not installing SC on prod or worker build'"

WORKDIR /code

ENTRYPOINT []
