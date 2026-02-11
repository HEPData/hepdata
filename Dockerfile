FROM python:3.9 as build

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
ARG SAUCE_OS

# https://github.com/nodesource/distributions#deb
ENV NODE_MAJOR=18
RUN curl -SLO https://deb.nodesource.com/nsolid_setup_deb.sh
RUN chmod 500 nsolid_setup_deb.sh
RUN ./nsolid_setup_deb.sh ${NODE_MAJOR}
RUN apt-get install nodejs -y

WORKDIR /code

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
 pip install --no-cache-dir --upgrade "setuptools<82" && \
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

RUN bash -c "set -x; [[ ${APP_ENVIRONMENT:-prod} = local-web ]] && (cd /usr/local/var && wget https://saucelabs.com/downloads/sauce-connect/5.3.1/sauce-connect-5.3.1_${SAUCE_OS:-linux.x86_64}.tar.gz && \
  tar -xvf sauce-connect-5.3.1_${SAUCE_OS:-linux.x86_64}.tar.gz) || echo 'Not installing SC on prod or worker build'"

WORKDIR /code

ENTRYPOINT []

# Copy "static" directory from "build" image to "statics" image, using "tar -h" to dereference symlinks.
RUN bash -c "cd /usr/local/var/hepdata-instance; tar -czhf /tmp/static.tar.gz static"

FROM nginx as statics
COPY --from=build /tmp/static.tar.gz /tmp/static.tar.gz
RUN bash -c "tar -xzf /tmp/static.tar.gz -C /usr/share/nginx/html"
COPY robots.txt /usr/share/nginx/html/robots.txt
