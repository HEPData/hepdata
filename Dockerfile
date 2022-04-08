FROM python:3.8

WORKDIR /usr/src/app

ENV PYTHONBUFFERED=0 \
    SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
    REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"

COPY certs/CERN_Root_Certification_Authority_2.pem /usr/local/share/ca-certificates/CERN_Root_Certification_Authority_2.crt
COPY certs/CERN_Grid_Certification_Authority.crt /usr/local/share/ca-certificates/CERN_Grid_Certification_Authority.crt

RUN update-ca-certificates \
 && pip config set global.cert "${REQUESTS_CA_BUNDLE}"

ENTRYPOINT [ "python3" ]
CMD [ "--version" ]

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
