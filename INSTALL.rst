Installation
============

First install HEPData all requirements:

.. code-block:: console

   $ mkvirtualenv hepdata3
   (hepdata3)$ pip install -r requirements.txt --pre --src ~/src/ --exists-action i
   (hepdata3)$ pip install -e .[postgresql]

Next, install and build assets:

.. code-block:: console

   (hepdata3)$ npm update && npm install --silent -g node-sass clean-css uglify-js requirejs
   (hepdata3)$ hepdata npm
   (hepdata3)$ cdvirtualenv var/hepdata-instance/static
   (hepdata3)$ npm install
   (hepdata3)$ hepdata collect -v
   (hepdata3)$ hepdata assets build


Next, create the database and database tables if you haven't already done so:

.. code-block:: console

   (hepdata3)$ hepdata db init
   (hepdata3)$ hepdata db create

Run Celery

.. code-block:: console

   (hepdata3)$ celery worker -E -A hepdata.celery


Now, start HEPData:

.. code-block:: console

   (hepdata3)$ hepdata --debug run


Run using honcho
============

Honcho will run elasticsearch, redis, celery, and the web application for you automatically.
Just workon your virtual environment, go to the root directory of hepdata source where you can see a file called
Procfile. Then install flower if you haven't done so already, and then start honcho.

.. code-block:: console

   (hepdata3)$ pip install flower
   (hepdata3)$ honcho start
