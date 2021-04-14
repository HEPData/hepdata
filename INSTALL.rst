##################
Installation
##################

 * :ref:`options-for-installing`
 * :ref:`running-services-locally`
 * :ref:`running-docker-compose`
 * :ref:`development-tips`

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
 * `PostgreSQL <http://www.postgresql.org/>`_ (version 9.6) database server
 * `Redis <http://redis.io/>`_ for caching
 * `Elasticsearch <https://www.elastic.co/products/elasticsearch>`_ (version 7.1, not later versions) for indexing and information retrieval. See below for further instructions.
 * `Node.js <https://nodejs.org>`_ JavaScript run-time environment and its package manager `npm <https://www.npmjs.com/>`_. (If you're using a Debian-based OS, please follow the `official installation instructions <https://github.com/nodesource/distributions/blob/master/README.md#debinstall>`_ to install NodeJS (which will also install npm), to avoid issues with ``node-sass``.)

These services can be installed using the relevant package manager for your system,
for example, using ``yum`` or ``apt-get`` for Linux or ``brew`` for macOS.

Elasticsearch
-------------

See the `installation instructions <https://www.elastic.co/guide/en/elasticsearch/reference/7.1/install-elasticsearch.html>`_
for installing ElasticSearch 7.1, but be aware that the instructions for Homebrew (for macOS) will install version 7.6 by default. To
install v7.1 via Homebrew, run:

.. code-block:: console

    $ brew tap elastic/tap
    $ cd $(brew --repo elastic/tap)
    $ git checkout f90d9a385d44917aee879695c7168a0ca4dc6079
    $ HOMEBREW_NO_AUTO_UPDATE=1 brew install elasticsearch-oss

Alternatively, run Elasticsearch after `installing Docker <https://docs.docker.com/install/>`_ with:

.. code-block:: console

    $ docker pull docker.elastic.co/elasticsearch/elasticsearch:7.1.1
    $ docker run -d -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.1.1

.. _installation:

Installation
============

Python
------
The HEPData code is only compatible with Python 3 (not Python 2).  It has been tested with Python 3.6.

First install all requirements in a `virtualenv <https://virtualenv.pypa.io/en/stable/installation.html>`_
using `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_:

.. code-block:: console

   $ mkvirtualenv hepdata
   (hepdata)$ mkdir ~/src/
   (hepdata)$ cd ~/src/
   (hepdata)$ git clone https://github.com/HEPData/hepdata.git
   (hepdata)$ cd hepdata
   (hepdata)$ pip install --upgrade pip
   (hepdata)$ pip install -e .[all] --upgrade -r requirements.txt

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
   CFG_TMPDIR = '/mt/home/watt/tmp/hepdata/tmp'
   CFG_DATADIR = '/mt/home/watt/tmp/hepdata/data'

An example file ``hepdata/config_local.local.py`` is provided, which can be copied to ``hepdata/config_local.py``.

JavaScript
----------

Next, build assets using webpack (via `invenio-assets <https://invenio-assets.readthedocs.io/en/latest/>`_).

.. code-block:: console

   (hepdata)$ ./scripts/clean_assets.sh

Celery
------

Run Celery (-B runs celery beat):

.. code-block:: console

   (hepdata)$ celery worker -l info -E -B -A hepdata.celery -Q celery,priority

PostgreSQL
----------

See `YUM Installation <https://wiki.postgresql.org/wiki/YUM_Installation>`_ and
`First steps <https://wiki.postgresql.org/wiki/First_steps>`_.

.. code-block:: console

   $ sudo su - postgres
   -$ createuser hepdata --createdb --pwprompt
   Enter password for new role: hepdata
   Enter it again: hepdata
   -$ createdb hepdata -O hepdata
   -$ createdb hepdata_test -O hepdata
   -$ exit

Next, create the database and database tables.
Also create a user and populate the database with some records.
Pass your email address and a password as an argument to the script:

.. code-block:: console

   (hepdata)$ ./scripts/initialise_db.sh your@email.com password

Inspect the ``hepdata`` database from the command line as the ``hepdata`` user:

.. code-block:: console

   $ psql hepdata -U hepdata -h localhost
   Password for user hepdata: hepdata
   hepdata=> select publication_recid, inspire_id, last_updated from hepsubmission;

    publication_recid | inspire_id |    last_updated
   -------------------+------------+---------------------
                    1 | 1283842    | 2016-07-13 15:12:45
                    2 | 1245023    | 2013-12-17 10:35:06
                   57 | 1311487    | 2016-02-12 18:45:16
   (3 rows)

   hepdata=> \q

If you're having problems with access permissions to the database, a simple solution is to edit the
PostgreSQL Client Authentication Configuration File (e.g. ``/var/lib/pgsql/9.6/data/pg_hba.conf``) to
``trust`` local and IPv4/IPv6 connections (instead of ``peer`` or ``ident``), then restart the PostgreSQL
server (e.g. ``sudo systemctl restart postgresql-9.6``).

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

Some of the tests run using `Selenium <https://selenium.dev>`_ on `Sauce Labs <https://saucelabs.com>`_. To run the tests
locally you have several options:

1. Run a Sauce Connect tunnel (recommended).
    1. Create a Sauce Labs account, or ask for the HEPData account details.
    2. Log into Sauce Labs, and go to the "Tunnels" page.
    3. Follow the instructions there to install Sauce Connect and start a tunnel.
    4. Create the variables ``SAUCE_USERNAME`` and ``SAUCE_ACCESS_KEY`` in your local environment (and add them to your
       bash profile).

2. Run Selenium locally using ChromeDriver.
    1. Install `ChromeDriver <https://chromedriver.chromium.org>`_
       (matched to your version of `Chrome <https://www.google.com/chrome/>`_).
    2. Include ``RUN_SELENIUM_LOCALLY = True`` and ``RATELIMIT_ENABLED = False`` in your ``hepdata/config_local.py`` file.
    3. You might need to close Chrome before running the end-to-end tests.

3. Omit the end-to-end tests when running locally, by running ``pytest tests -k 'not tests/e2e'`` instead of ``run-tests.sh``.


Once you have set up Selenium or Sauce Labs, you can run the tests using:

.. code-block:: console

   (hepdata)$ cd ~/src/hepdata
   (hepdata)$ ./run-tests.sh

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

For local development you can use the ``docker-compose.yml`` file to run the HEPData docker image and its required services.

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

   $ docker-compose exec web bash -c "/usr/local/var/sc-4.5.4-linux/bin/sc -u $SAUCE_USERNAME -k $SAUCE_ACCESS_KEY -x https://eu-central-1.saucelabs.com/rest/v1 & ./run-tests.sh"


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


.. _development-tips:

****************
Development Tips
****************

JavaScript/Webpack
==================

The JavaScript and CSS are bundled using `Webpack <https://webpack.js.org>`_, via the following packages:

 * `pywebpack <https://pywebpack.readthedocs.io/en/latest/>`_ provides a way to define Webpack bundles in python.
 * `Flask-WebpackExt <https://flask-webpackext.readthedocs.io/en/latest/>`_ integrates `pywebpack` with Flask. It provides the `WebpackBundle` class used to define the entry points and contents of the Webpack packages, and the ``{{ webpack[...] }}`` template function used to inject javascript and css into a page.
 * `invenio-assets <https://invenio-assets.readthedocs.io/en/latest/>`_ integrates Flask-WebpackExt with Invenio and provides a CLI command to collect the assets.

Each module that requires javascript has a ``webpack.py`` file which list the JavaScript files and their dependencies. Dependencies need to be imported at the top of each JavaScript file. To add a new JavaScript file:

 1. Create the file in ``<module>/assets/js``.
 2. Edit ``<module>/webpack.py`` and add an item to the ``entries`` dict, e.g.

 .. code-block:: python

    'hepdata-reviews-js': './js/hepdata_reviews.js',

 3. To include the file in another JavaScript file, use e.g.

 .. code-block:: javascript

    import HEPDATA from './hepdata_common.js' // Puts HEPDATA in the namespace
    import './hepdata_reviews.js' // Adds functions to HEPDATA from hepdata_reviews

 4. To include the file in an HTML page, use the ``webpack`` function with the name from ``'entries'`` in ``bundle.py``, with a ``.js`` extension. (Similarly, CSS files can be included using a ``.css`` extension.)

 .. code-block:: html

    {{ webpack['hepdata-reviews-js.js'] }}

If you need to add a new bundle, it will need to be added to the ``'invenio_assets.webpack'`` entry in ``setup.py`` (and you will need to re-run ``pip install -e.[all] hepdata``).

When making changes to the javascript you may find it helpful to build the javascript on-the-fly:

.. code-block:: console

   (hepdata)$ cd $HOME/.virtualenvs/hepdata/var/hepdata-instance/assets
   (hepdata)$ npm start

If you want to build all of the JavaScript, run:

.. code-block:: console

   (hepdata)$ hepdata webpack build

If you have made a change to a ``webpack.py`` file, run:

.. code-block:: console

   (hepdata)$ hepdata webpack buildall

Occasionally the Webpack build will complete but there will be errors higher up in the output. If the JavaScript file
does not load in the page (e.g. you see a ``KeyError: not in manifest.json`` error), check the webpack build output.

npm dependency issues
---------------------

If you have issues with npm peer dependencies when running ``hepdata webpack buildall``, (e.g. an error message starting
``ERESOLVE unable to resolve dependency tree`` and followed by ``Could not result dependency: peer ...``) then you will
need to set the `legacy-peer-deps <https://docs.npmjs.com/cli/v7/using-npm/config#legacy-peer-deps>`_ flag for npm.
There are two ways to do this:

**Either:**

Set the flag globally in your npm config (NB: this will affect other npm projects):

.. code-block:: console

   (hepdata)$ npm config set legacy-peer-deps true

You will then be able to run ``hepdata webpack buildall``.

**Or:**

Run the webpack CLI ``install`` and ``build`` commands separately (rather than using ``buildall``) and pass ``--legacy-peer-deps`` to the npm install step:

.. code-block:: console

   (hepdata)$ hepdata webpack install --legacy-peer-deps
   (hepdata)$ hepdata webpack build
