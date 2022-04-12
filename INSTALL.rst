##################
Installation
##################

 * :ref:`options-for-installing`
 * :ref:`running-services-locally`
 * :ref:`running-docker-compose`

.. _options-for-installing:

**********************
Options for installing
**********************

There are two ways to get HEPData running locally: either install and run all the services on your local machine, or
run it via `Docker Compose <https://docs.docker.com/compose/>`__.

Using ``docker-compose`` is the quickest way to get up-and-running. However, it has some disadvantages:
 * It requires more resources on your local machine as it runs several Docker containers.
 * It can be slightly trickier to run commands and debug.
 * The tests take longer to run, particularly the end-to-end tests.

.. _running-services-locally:

************************
Running services locally
************************

Prerequisites
=============

HEPData uses several services, which you will need to install before running HEPData:
 * `PostgreSQL <http://www.postgresql.org/>`_ (version 12) database server
 * `Redis <http://redis.io/>`_ for caching
 * `Elasticsearch <https://www.elastic.co/products/elasticsearch>`_ (version 7) for indexing and information retrieval. See below for further instructions.
 * `Node.js <https://nodejs.org>`_ (version 14) JavaScript run-time environment and its package manager `npm <https://www.npmjs.com/>`_. (If you're using a Debian-based OS, please follow the `official installation instructions <https://github.com/nodesource/distributions/blob/master/README.md#debinstall>`_ to install NodeJS (which will also install npm), to avoid issues with ``node-sass``.)

These services can be installed using the relevant package manager for your system,
for example, using ``yum`` or ``apt-get`` for Linux or ``brew`` for macOS.

Elasticsearch
-------------

Currently we use v7.10.2 on our QA cluster (via Open Distro v1.13.2) and v7.1.1 in production. You can choose which version
to install but if you install v7.10, be careful to avoid using features of Elasticsearch that are not available in v7.1.

**Elasticsearch v7.1.1**
~~~~~~~~~~~~~~~~~~~~~~~~

See the `installation instructions <https://www.elastic.co/guide/en/elasticsearch/reference/7.1/install-elasticsearch.html>`_
for installing ElasticSearch 7.1, but be aware that the instructions for Homebrew (for macOS) will install a newer version by default. To
install v7.1 via Homebrew, run:

.. code-block:: console

    $ brew tap elastic/tap
    $ cd $(brew --repo elastic/tap)
    $ git checkout f90d9a3
    $ HOMEBREW_NO_AUTO_UPDATE=1 brew install elasticsearch-oss

Alternatively, run Elasticsearch after `installing Docker <https://docs.docker.com/install/>`_ with:

.. code-block:: console

    $ docker pull docker.elastic.co/elasticsearch/elasticsearch:7.1.1
    $ docker run -d -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.1.1

**Elasticsearch v7.10.2 / Open Distro v1.13.2**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `Open Distro instructions <https://opendistro.github.io/for-elasticsearch/>`_ give details on how to install for Linux
and Windows. They suggest using Docker for macOS:

.. code-block:: console

    $ docker pull amazon/opendistro-for-elasticsearch:1.13.2
    $ docker run -d -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" -e "opendistro_security.disabled=true" amazon/opendistro-for-elasticsearch:1.13.2

To run outside of Docker you can use the Homebrew installation of Elasticsearch 7.10.2:

.. code-block:: console

    $ brew install elasticsearch

Neither of these two methods is currently working for an M1 MacBook, so use Elasticsearch v7.1.1 for now.

.. _installation:

Installation
============

Python
------
The HEPData code is only compatible with Python 3 (not Python 2).  It has been tested with Python 3.6.
It has also been tested with Python 3.8 on an M1 MacBook where some changes were required (documented below).

First install all requirements in a `virtualenv <https://virtualenv.pypa.io/en/stable/installation.html>`_.
(Use `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_ if you prefer.)
The instructions below use ``virtualenv`` directly (Python module `venv <https://docs.python.org/3/library/venv.html>`_)
with a target directory also called ``venv`` (change it if you prefer).

.. code-block:: console

   $ git clone https://github.com/HEPData/hepdata.git
   $ cd hepdata
   $ python3 -m venv venv
   $ source venv/bin/activate
   (venv)$ pip install --upgrade pip
   (venv)$ pip install -e ".[all]" --upgrade -r requirements.txt

Check that PyYAML has been installed with LibYAML bindings:

.. code-block:: console

   (venv)$ python -c "from yaml import CSafeLoader"

If LibYAML is already installed (e.g. ``brew install libyaml``) but ``CSafeLoader`` cannot be imported, you may need to
reinstall PyYAML to ensure it's built with LibYAML bindings, e.g. on an M1 MacBook:

.. code-block:: console

   (venv)$ LDFLAGS="-L$(brew --prefix)/lib" CFLAGS="-I$(brew --prefix)/include" pip install --global-option="--with-libyaml" --force pyyaml==5.4.1


Use of config_local.py
----------------------

The ``hepdata/config.py`` contains default configuration options, which often need to be overridden in a local instance.
For example, DOI minting should be switched off in a non-production instance, otherwise finalising a new record will
give an error message due to a lack of DataCite authorisation credentials.
Rather than edit ``hepdata/config.py``, it is more convenient to define custom options in a separate file
``hepdata/config_local.py`` that will be ignored by Git.  For example, to switch off email, DOI minting, Twitter,
use a local converter URL, and specify custom temporary and data directories:

.. code-block:: python

   SITE_URL = "http://localhost:5000"
   TESTING = True
   NO_DOI_MINTING = True
   USE_TWITTER = False
   CFG_CONVERTER_URL = 'http://localhost:5500'
   CFG_TMPDIR = '/Users/watt/tmp/hepdata/tmp'
   CFG_DATADIR = '/Users/watt/tmp/hepdata/data'

An example file ``hepdata/config_local.local.py`` is provided, which can be copied to ``hepdata/config_local.py``.

JavaScript
----------

Next, build assets using webpack (via `invenio-assets <https://invenio-assets.readthedocs.io/en/latest/>`_).

.. code-block:: console

   (hepdata)$ ./scripts/clean_assets.sh

On an M1 MacBook, until an `issue with Invenio-Assets <https://github.com/inveniosoftware/invenio-assets/issues/144>`_
is addressed, you will need to replace
``"node-sass": "^4.12.0",`` with ``"sass": "^1.50.0",`` (or another `Dart Sass <https://sass-lang.com/dart-sass>`_
version) in the ``package.json`` file of the ``invenio-assets`` installation
(e.g. ``venv/lib/python3.8/site-packages/invenio_assets/assets/package.json``).

Celery
------

Run Celery (-B runs celery beat):

.. code-block:: console

   (hepdata)$ celery -A hepdata.celery worker -l info -E -B -Q celery,priority,datacite

PostgreSQL
----------

See `YUM Installation <https://wiki.postgresql.org/wiki/YUM_Installation>`_ and
`First steps <https://wiki.postgresql.org/wiki/First_steps>`_.  On Linux you might need ``sudo su - postgres`` before
executing the steps below.  On macOS you can install with ``brew install postgresql@12``.

.. code-block:: console

   $ createuser hepdata --createdb --pwprompt
   Enter password for new role: hepdata
   Enter it again: hepdata
   $ createdb hepdata -O hepdata
   $ createdb hepdata_test -O hepdata

Next, create the database and database tables.
Also create a user and populate the database with some records.
Make sure that Celery is running before proceeding further.
Until an `issue <https://github.com/HEPData/hepdata/issues/461>`_ is addressed and ``Invenio-Accounts`` is upgraded
to at least v1.4.9, you will need to manually
`patch <https://github.com/inveniosoftware/invenio-accounts/commit/b91649244b11479d8fa817745141c0027001dff1>`_
the ``invenio_accounts/cli.py`` file (e.g. ``venv/lib/python3.8/site-packages/invenio_accounts/cli.py``) before the
next step.  Pass your email address and a password as an argument to the script:

.. code-block:: console

   (hepdata)$ ./scripts/initialise_db.sh your@email.com password

Inspect the ``hepdata`` database from the command line as the ``hepdata`` user:

.. code-block:: console

   $ psql hepdata -U hepdata -h localhost
   Password for user hepdata: hepdata

   hepdata=> select publication_recid, inspire_id, last_updated from hepsubmission order by publication_recid;
    publication_recid | inspire_id |    last_updated
   -------------------+------------+---------------------
                    1 | 1245023    | 2013-12-17 10:35:06
                    2 | 1283842    | 2014-08-11 17:25:55
                    3 | 1311487    | 2016-02-12 18:45:16
                   58 | 1299143    | 2014-08-05 17:55:54
   (4 rows)

If you're having problems with access permissions to the database (on Linux), a simple solution is to edit the
PostgreSQL Client Authentication Configuration File (e.g. ``/var/lib/pgsql/12/data/pg_hba.conf``) to
``trust`` local and IPv4/IPv6 connections (instead of ``peer`` or ``ident``), then restart the PostgreSQL
server (e.g. ``sudo systemctl restart postgresql-12``).

Run a local development server
------------------------------

Now, switch Flask to the development environment and enable debug mode, then start the HEPData web application:

.. code-block:: console

   (hepdata)$ export FLASK_ENV=development
   (hepdata)$ hepdata run --debugger --reload
   (hepdata)$ firefox http://localhost:5000/

.. _running-the-tests:


Running the tests
-----------------

Some of the tests run using `Selenium <https://selenium.dev>`_ on `Sauce Labs <https://saucelabs.com>`_.
Note that some of the end-to-end tests currently fail when run individually rather than all together.
To run the tests locally you have several options:

1. Run a Sauce Connect tunnel (recommended).  This is used by GitHub Actions CI.
    1. Create a Sauce Labs account, or ask for the HEPData account details.
    2. Log into Sauce Labs, and go to the "Tunnels" page.
    3. Follow the instructions there to install Sauce Connect and start a tunnel.
       Do not name the tunnel with the ``--tunnel-name`` argument.
    4. Create the variables ``SAUCE_USERNAME`` and ``SAUCE_ACCESS_KEY`` in your local environment (and add them to your
       bash or zsh profile).

2. Run Selenium locally using ChromeDriver.  (Some tests are currently failing with this method.)
    1. Install `ChromeDriver <https://chromedriver.chromium.org>`_
       (matched to your version of `Chrome <https://www.google.com/chrome/>`_).
    2. Include ``RUN_SELENIUM_LOCALLY = True`` and ``RATELIMIT_ENABLED = False`` in your ``hepdata/config_local.py`` file.
    3. You might need to close Chrome before running the end-to-end tests.

3. Omit the end-to-end tests when running locally, by running ``pytest tests -k 'not tests/e2e'`` instead of ``run-tests.sh``.


Once you have set up Selenium or Sauce Labs, you can run the tests using:

.. code-block:: console

   (venv)$ ./run-tests.sh

Docker for hepdata-converter-ws
-------------------------------

To get the file conversion working from the web application (such as automatic conversion from ``.oldhepdata`` format),
you can use the default ``CFG_CONVERTER_URL = https://converter.hepdata.net`` even outside the CERN network.
Alternatively, after `installing Docker <https://docs.docker.com/install/>`_, you can run a local Docker container:

.. code-block:: console

   docker pull hepdata/hepdata-converter-ws
   docker run --restart=always -d --name=hepdata_converter -p 0.0.0.0:5500:5000 hepdata/hepdata-converter-ws hepdata-converter-ws

then specify ``CFG_CONVERTER_URL = 'http://localhost:5500'`` in ``hepdata/config_local.py`` (see above).


.. _running-docker-compose:

**************************
Running via docker-compose
**************************

The Dockerfile is used by GitHub Actions CI to build a Docker image and push to DockerHub ready for deployment in production
on the Kubernetes cluster at CERN.

For local development you can use the ``docker-compose.yml`` file to run the HEPData Docker image and its required services.

First, ensure you have installed `Docker <https://docs.docker.com/install/>`_ and `Docker Compose <https://docs.docker.com/compose/install/>`__.

Copy the file ``config_local.docker_compose.py`` to ``config_local.py``.

In order to run the tests via Sauce Labs, ensure you have the variables ``$SAUCE_USERNAME`` and ``$SAUCE_ACCESS_KEY``
set in your environment (see :ref:`running-the-tests`) **before** starting the containers.

Start the containers:

.. code-block:: console

   $ docker-compose up

(This starts containers for all the 5 necessary services. See :ref:`docker-compose-tips` if you only want to run some containers.)

In another terminal, initialise the database:

.. code-block:: console

   $ docker-compose exec web bash -c "mkdir -p /code/tmp; ./scripts/initialise_db.sh your@email.com password"

Now open http://localhost:5000/ and HEPData should be up and running. (It may take a few minutes for Celery to process
the sample records.)

To run the tests:

.. code-block:: console

   $ docker-compose exec web bash -c "/usr/local/var/sc-4.7.1-linux/bin/sc -u $SAUCE_USERNAME -k $SAUCE_ACCESS_KEY -x https://eu-central-1.saucelabs.com/rest/v1 & ./run-tests.sh"


.. _docker-compose-tips:

Tips
====

* If you see errors about ports already being allocated, ensure you're not running any of the services another way (e.g. hepdata-converter via Docker).
* If you want to run just some of the containers, specify their names in the docker-compose command. For example, to just run the web server, database and elasticsearch, run:

  .. code-block:: console

    $ docker-compose up web db es

  See ``docker-compose.yml`` for the names of each service. Running a subset of containers could be useful in the following cases:

   * You want to use the live converter service, i.e.  ``CFG_CONVERTER_URL = 'https://converter.hepdata.net'`` instead of running the converter locally.
   * You want to run the container for the web service by pulling an image from DockerHub instead of building an image locally.
   * You want to run containers for all services apart from web (and maybe converter) then use a non-Docker web service.

* To run the containers in the background, run:

  .. code-block:: console

     $ docker-compose up -d

  To see the logs you can then run:

  .. code-block:: console

     $ docker-compose logs

* To run a command on a container, run the following (replacing <container_name> with the name of the container as in ``docker-compose.yml``, e.g. ``web``):

  .. code-block:: console

    $ docker-compose exec <container_name> bash -c "<command>"

* If you need to run several commands, run the following to get a bash shell on the container:

  .. code-block:: console

     $ docker-compose exec <container_name> bash

* If you switch between using ``docker-compose`` and individual services, you may get an error when running the tests about an import file mismatch. To resolve this, run:

  .. code-block:: console

     $ find . -name '*.pyc' -delete
