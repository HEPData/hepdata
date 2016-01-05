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
