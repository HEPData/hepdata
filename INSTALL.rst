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

HEPData runs with Python 3.7, 3.8 or 3.9. It also uses several services, which you will need to install before running HEPData.

These services can be installed using the relevant package manager for your system,
for example, using ``yum`` or ``apt-get`` for Linux or ``brew`` for macOS:

 * `PostgreSQL <http://www.postgresql.org/>`_ (version 12) database server
 * `Redis <http://redis.io/>`_ for caching
 * `OpenSearch <https://opensearch.org/>`_ (version 2.7.0) for indexing and information retrieval. See below for further instructions.
 * `Node.js <https://nodejs.org>`_ (version 18) JavaScript run-time environment and its package manager `npm <https://www.npmjs.com/>`_.

OpenSearch v2.7.0
-----------------

We are currently using OpenSearch v2.7.0. Here, you can find the `download instructions. <https://opensearch.org/versions/opensearch-2-7-0.html>`_

There are some examples below:

**MacOS**

Install the latest version (currently, v2.8.0) with ``brew install opensearch``.
Alternatively, to install a specific version like v2.6.0 via Homebrew (v2.7.0 is unavailable), run:

.. code-block:: console

    $ brew tap-new opensearch/tap
    $ brew extract --version=2.6.0 opensearch opensearch/tap
    $ brew install opensearch/tap/opensearch@2.6.0
    $ brew services restart opensearch/tap/opensearch@2.6.0

**Linux**

You can see the tarball instructions on the OpenSearch installation `webpage. <https://opensearch.org/docs/2.2/opensearch/install/tar/>`_

To execute, run this command within the extracted folder.

.. code-block:: console

		./opensearch-tar-install.sh -E "plugins.security.disabled=true"

**Docker**

Alternatively, run OpenSearch after `installing Docker <https://docs.docker.com/install/>`_ with:

.. code-block:: console

    $ docker pull opensearchproject/opensearch:2.7.0
    $ docker run -d -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" -e "plugins.security.disabled=true" opensearchproject/opensearch:2.7.0

.. _installation:

Installation
============

Python
------
The HEPData code is only compatible with Python 3.7, 3.8 or 3.9 (not Python 2 or other 3.x versions).  We recommend Python 3.9.

First install all requirements in a Python virtual environment.
(Use `virtualenv <https://virtualenv.pypa.io/en/stable/installation.html>`_ or
`virtualenvwrapper <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_ if you prefer.)
The instructions below use the Python module `venv <https://docs.python.org/3/library/venv.html>`_ directly
with a target directory also called ``venv`` (change it if you prefer).

.. code-block:: console

   $ git clone https://github.com/HEPData/hepdata.git
   $ cd hepdata
   $ python3.9 -m venv venv
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

The next line sets environment variables to switch Flask to run in development mode.
You may want to set these automatically in your bash or zsh profile.

.. code-block:: console

   (venv)$ export FLASK_ENV=development
   (venv)$ export FLASK_DEBUG=1

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
Replace the CFG_TMPDIR and CFG_DATADIR directory values with a suitable path for your system.

With ``TESTING=True`` emails will be output to the terminal, but links are suppressed preventing some functionality
such as clicking on confirmation links when a new user is created (see
`HEPData/hepdata#493 <https://github.com/HEPData/hepdata/issues/493>`_).
With ``TESTING=False`` you will need to configure an SMTP server to send emails such as
`SMTP2GO <https://www.smtp2go.com>`_ that offers a free plan with a limit of 1000 emails/month.
An alternative is to install `MailCatcher <https://mailcatcher.me/>`_ (e.g. ``brew install mailcatcher``) where you
just need to add these lines to ``hepdata/config_local.py``:

.. code-block:: python

   MAIL_SERVER = '127.0.0.1'
   MAIL_PORT = 1025

JavaScript
----------

Next, build assets using webpack (via `invenio-assets <https://invenio-assets.readthedocs.io/en/latest/>`_).

.. code-block:: console

   (hepdata)$ ./scripts/clean_assets.sh

Celery
------

Run Celery and ensure the redis-server service is running (-B runs celery beat):

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
Pass an email address and any password as an argument to the script:

.. code-block:: console

   (hepdata)$ ./scripts/initialise_db.sh your@email.com password

Inspect the ``hepdata`` database from the command line as the ``hepdata`` user and add email confirmation:

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

Set email confirmation for the test user within the database.

.. code-block:: console

   hepdata=> update accounts_user set confirmed_at=NOW() where id=1;
   UPDATE 1

If you're having problems with access permissions to the database (on Linux), a simple solution is to edit the
PostgreSQL Client Authentication Configuration File (e.g. ``/var/lib/pgsql/12/data/pg_hba.conf``) to
``trust`` local and IPv4/IPv6 connections (instead of ``peer`` or ``ident``), then restart the PostgreSQL
server (e.g. ``sudo systemctl restart postgresql-12``).

Recreate the OpenSearch index
-----------------------------

You may need to recreate the OpenSearch data, for example, after switching to a new OpenSearch instance.

.. code-block:: console

   (hepdata) $ hepdata utils reindex -rc True

Run a local development server
------------------------------

Now start the HEPData web application in debug mode:

.. code-block:: console

   (hepdata)$ hepdata run --debugger --reload

Then open your preferred web browser (Chrome, Firefox, Safari, etc.) at http://localhost:5000/ .

On macOS Monterey you might find that ControlCenter is already listening to port 5000
(check with ``lsof -i -P | grep 5000``).  If this is the case,
`turn off AirPlay Receiver <https://support.apple.com/en-gb/guide/mac-help/mchl15c9e4b5/12.0/mac/12.0>`_.


.. _running-the-tests:


Running the tests
-----------------

Some of the tests run using `Selenium <https://selenium.dev>`_ on `Sauce Labs <https://saucelabs.com>`_.
Note that some of the end-to-end tests currently fail when run individually rather than all together.

To run the tests locally you have several options:

1. Run a Sauce Connect tunnel (recommended).  This is used by GitHub Actions CI.
    1. Create a Sauce Labs account, or ask for the HEPData account details.
    2. Log into Sauce Labs, and go to the "Tunnel Proxies" page.
    3. Follow the instructions there to install Sauce Connect and start a tunnel.
       Do not name the tunnel with the ``--tunnel-name`` argument.
    4. Create the variables ``SAUCE_USERNAME`` and ``SAUCE_ACCESS_KEY`` in your local environment (and add them to your
       bash or zsh profile).

2. Run Selenium locally using ChromeDriver.  (Some tests are currently failing with this method.)
    1. Install `ChromeDriver <https://chromedriver.chromium.org>`_
       (matched to your version of `Chrome <https://www.google.com/chrome/>`_).
    2. Include ``RUN_SELENIUM_LOCALLY = True`` in your ``hepdata/config_local.py`` file.
    3. You might need to close Chrome before running the end-to-end tests.

3. Omit the end-to-end tests when running locally, by running ``pytest tests -k 'not tests/e2e'`` instead of ``run-tests.sh``.


Once you have set up Selenium or Sauce Labs, you can run the tests using:

.. code-block:: console

   (venv)$ ./run-tests.sh

Note that the end-to-end tests require the converter (specified by ``CFG_CONVERTER_URL``) to be running.


NOTE: To test changes to `ci.yml <https://github.com/HEPData/hepdata/blob/main/.github/workflows/ci.yml>`_ locally,
you can use `act <https://github.com/nektos/act>`_.  A ``.secrets`` file should be created in the project root
directory with the variables ``SAUCE_USERNAME`` and ``SAUCE_ACCESS_KEY`` set in order to run the end-to-end tests.
Only one ``matrix`` configuration will be used to avoid problem with conflicting ports.  Running ``act -n`` is useful
for dryrun mode.


Building the docs
-----------------

If any changes were to be made to the installation docs, to check docs can be locally built use:

.. code-block:: console

   (venv)$ cd docs
   (venv)$ make html
   (venv)$ open _build/html/index.html


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

First, ensure you have installed `Docker <https://docs.docker.com/install/>`_ and `Docker Compose <https://docs.docker.com/compose/install/>`_.

Copy the file ``config_local.docker_compose.py`` to ``config_local.py``.

In order to run the tests via Sauce Labs, ensure you have the variables ``$SAUCE_USERNAME`` and ``$SAUCE_ACCESS_KEY``
set in your environment (see :ref:`running-the-tests`) **before** starting the containers.

If using an M1 MacBook, also add ``export SAUCE_OS=linux-arm64`` to your bash or zsh profile. This is necessary to
download the correct `Sauce Connect Proxy
<https://docs.saucelabs.com/secure-connections/sauce-connect/installation/#downloading-sauce-connect-proxy>`_
client.

Start the containers:

.. code-block:: console

   $ docker-compose up

(This starts containers for all the 6 necessary services. See :ref:`docker-compose-tips` if you only want to run some containers.)

In another terminal, initialise the database:

.. code-block:: console

   $ docker-compose exec web bash -c "hepdata utils reindex -rc True"  # ignore error "hepsubmission" does not exist
   $ docker-compose exec web bash -c "mkdir -p /code/tmp; ./scripts/initialise_db.sh your@email.com password"
   $ docker-compose exec db bash -c "psql hepdata -U hepdata -c 'update accounts_user set confirmed_at=NOW() where id=1;'"

Now open http://localhost:5000/ and HEPData should be up and running. (It may take a few minutes for Celery to process
the sample records.)

To run the tests:

.. code-block:: console

   $ docker-compose exec web bash -c "/usr/local/var/sc-4.9.1-${SAUCE_OS:-linux}/bin/sc -u $SAUCE_USERNAME -k $SAUCE_ACCESS_KEY --region eu-central & ./run-tests.sh"

.. _docker-compose-tips:

Tips
====

* If you see errors about ports already being allocated, ensure you're not running any of the services another way (e.g. hepdata-converter via Docker).
* If you want to run just some of the containers, specify their names in the ``docker-compose`` command. For example, to just run the web server, database and OpenSearch, run:

  .. code-block:: console

    $ docker-compose up web db os

  See ``docker-compose.yml`` for the names of each service. Running a subset of containers could be useful in the following cases:

   * You want to use the live converter service, i.e.  ``CFG_CONVERTER_URL = 'https://converter.hepdata.net'`` instead of running the converter locally.
   * You want to run the container for the web service by pulling an image from Docker Hub instead of building an image locally.
   * You want to run containers for all services apart from web (and maybe converter) then use a non-Docker web service.

  If using Docker Desktop, you need to use ``host.docker.internal`` instead of ``localhost`` when `connecting from a
  container to a service on the host <https://docs.docker.com/desktop/networking/#use-cases-and-workarounds-for-all-platforms>`_.

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
