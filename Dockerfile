#
# HEPData production docker build
#
FROM python:3.5
MAINTAINER HEPData <info@hepdata.net>

# Node.js, bower, less, clean-css, uglify-js, requirejs
RUN apt-get update
RUN apt-get -qy upgrade --fix-missing --no-install-recommends
RUN apt-get -qy install --fix-missing --no-install-recommends curl
RUN curl -sL https://deb.nodesource.com/setup_iojs_2.x | bash -

# Install dependencies
RUN apt-get -qy install --fix-missing --no-install-recommends gcc git iojs

# Slim down image
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg}/
RUN find /usr/share/doc -depth -type f ! -name copyright -delete
RUN find /usr/share/doc -empty -delete
RUN rm -rf /usr/share/man/* /usr/share/groff/* /usr/share/info/*

# Basic Python and Node.js tools
RUN pip install --upgrade pip setuptools ipython gunicorn
RUN npm update && npm install --silent -g node-sass clean-css uglify-js requirejs

#
# HEPData specific
#

# Pre-install modules for caching
RUN mkdir -p /usr/local/src/

# Create instance/static folder
ENV APP_INSTANCE_PATH /usr/local/var/invenio-instance/static/
RUN mkdir -p ${APP_INSTANCE_PATH}

# Copy source code
COPY . /code
WORKDIR /code

# Install HEPData
RUN pip install -r requirements.txt --src /usr/local/src
RUN python -O -m compileall .

# Slim down image
RUN rm -rf /tmp/* /var/tmp/* /var/lib/{cache,log}/ /root/.cache/*

# Install bower dependencies and build assets.
RUN hepdata npm
WORKDIR ${APP_INSTANCE_PATH}
RUN npm install
WORKDIR /code
RUN hepdata collect -v
RUN hepdata assets build

RUN adduser --uid 1000 --disabled-password --gecos '' hepdata
RUN chown -R hepdata:hepdata /code /usr/local/var/invenio-instance

VOLUME ["/code"]

USER hepdata

CMD ["hepdata", "run", "-h", "0.0.0.0"]
