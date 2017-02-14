Installation
============

First install all requirements:

.. code-block:: console

   $ mkvirtualenv hepdata
   (hepdata)$ mkdir ~/src/
   (hepdata)$ cd ~/src/
   (hepdata)$ git clone https://github.com/HEPData/hepdata
   (hepdata)$ cd hepdata
   (hepdata)$ pip install -e . --pre --upgrade

Next, install and build assets:

.. code-block:: console

   (hepdata)$ npm update && npm install --silent -g node-sass@3.8.0 clean-css uglify-js requirejs
   (hepdata)$ ./scripts/clean_assets.sh

Run Celery (-B runs celery beat):

.. code-block:: console

   (hepdata)$ celery worker -E -B -A hepdata.celery

Next, create the database and database tables if you haven't already done so.
Also create a user and populate the database with some records.
Pass your email address and a password as an argument to the script:

.. code-block:: console

   (hepdata)$ ./scripts/initialise_db.sh your@email.com password

Now, start HEPData:

.. code-block:: console

   (hepdata)$ hepdata run --debugger --reload
   (hepdata)$ firefox http://localhost:5000/


Run using honcho
================

Honcho will run elasticsearch, redis, celery, and the web application for you automatically.
Just workon your virtual environment, go to the root directory of hepdata source where you can see a file called
Procfile. Then install flower if you haven't done so already, and then start honcho.

.. code-block:: console

   (hepdata)$ pip install flower
   (hepdata)$ honcho start
