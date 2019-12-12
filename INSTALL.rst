Prerequisites
=============

HEPData uses several services such as the `PostgreSQL <http://www.postgresql.org/>`_
(version 9.6) database server, `Redis <http://redis.io/>`_ for caching, and `Elasticsearch
<https://www.elastic.co/products/elasticsearch>`_ (version 2.x, not later versions) for indexing and information
retrieval.  It also requires the `Node.js <https://nodejs.org>`_ JavaScript run-time environment
and its package manager `npm <https://www.npmjs.com/>`_.  These services can be installed using the
relevant package manager for your system, for example, using ``yum`` or ``apt-get`` for Linux or
``brew`` for macOS.


.. _installation:

Installation
============

Python
------

First install all requirements in a `virtualenv <https://virtualenv.pypa.io/en/stable/installation/>`_
using `virtualenvwrapper <https://virtualenvwrapper.readthedocs.io/en/latest/install.html>`_:

.. code-block:: console

   $ mkvirtualenv hepdata
   (hepdata)$ mkdir ~/src/
   (hepdata)$ cd ~/src/
   (hepdata)$ git clone https://github.com/HEPData/hepdata
   (hepdata)$ cd hepdata
   (hepdata)$ pip install --upgrade pip
   (hepdata)$ pip install -e . --pre --upgrade -r requirements.txt

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

JavaScript
----------

Next, install Node JavaScript packages in global mode using ``sudo npm install -g`` and build assets.  Note that
installing in local mode causes problems and it is necessary to run the install command outside your home directory.

.. code-block:: console

   (hepdata)$ cd /
   (hepdata)$ sudo npm install -g node-sass clean-css@3.4.28 uglify-js requirejs
   (hepdata)$ cd ~/src/hepdata
   (hepdata)$ ./scripts/clean_assets.sh

Celery
------

Run Celery (-B runs celery beat):

.. code-block:: console

   (hepdata)$ celery worker -E -B -A hepdata.celery

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

Now, start HEPData:

.. code-block:: console

   (hepdata)$ hepdata run --debugger --reload
   (hepdata)$ firefox http://localhost:5000/

Running the tests
-----------------

Run the tests using:

.. code-block:: console

   (hepdata)$ cd ~/src/hepdata
   (hepdata)$ ./run-tests.sh

Docker for hepdata-converter-ws
-------------------------------

If deploying inside CERN, you can use the default ``CFG_CONVERTER_URL = 'http://188.184.65.191'``.  Otherwise, to get the
file conversion working from the web application (such as automatic conversion from ``.oldhepdata`` format), you will
need to run a local Docker container.  After `installing Docker <https://docs.docker.com/install/>`_, run:

.. code-block:: console

   docker pull hepdata/hepdata-converter-ws
   docker run --restart=always -d --name=hepdata_converter -p 0.0.0.0:5500:5000 hepdata/hepdata-converter-ws hepdata-converter-ws

then specify ``CFG_CONVERTER_URL = 'http://localhost:5500'`` (see above).


Run using honcho
----------------

Note added: I haven't tested if this method works.

Honcho will run elasticsearch, redis, celery, and the web application for you automatically.
Just workon your virtual environment, go to the root directory of hepdata source where you can see a file called
Procfile. Then install flower if you haven't done so already, and then start honcho.

.. code-block:: console

   (hepdata)$ pip install flower
   (hepdata)$ honcho start


Run using Docker
----------------

A Dockerfile is provided in the HEPData/hepdata repository, inherited from the original Zenodo fork in 2015, but I don't think it ever worked.
There is also a separate HEPData/hepdata-docker repository from 2015, which has not been kept up-to-date (for example, it uses MySQL instead of PostgreSQL).
It would be good to come back to this in the future and get a working Docker installation.
