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

WORKDIR /code
