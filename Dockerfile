FROM inspirehep/python:2.7

RUN yum install -y xrootd-client -

WORKDIR /code

COPY requirements.txt .
COPY requirements-xrootd.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade setuptools && \
    pip install --no-cache-dir --upgrade wheel && \
    pip install -r requirements.txt -r requirements-xrootd.txt --pre

COPY . .
RUN pip install -e .

WORKDIR  /usr/var/hepdata-instance/static

RUN hepdata npm \
    && npm install \
    && hepdata collect -v \
    && hepdata assets build

WORKDIR /code
