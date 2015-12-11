Installation
============

First install HEPData all requirements:

.. code-block:: console

   $ mkvirtualenv hepdata3
   (zenodo3)$ pip install -r requirements.txt --pre --src ~/src/ --exists-action i
   (zenodo3)$ pip install -e .[postgresql]


Next, install and build assets:

.. code-block:: console

   (zenodo3)$ hepdata npm
   (zenodo3)$ cdvirtualenv var/hepdata-instance/static
   (zenodo3)$ npm install
   (zenodo3)$ hepdata collect -v
   (zenodo3)$ hepdata assets build


Next, create the database and database tables if you haven't already done so:

.. code-block:: console

   (zenodo3)$ hepdata db init
   (zenodo3)$ hepdata db create

Now, start HEPData:

   (zenodo3)$ hepdata --debug run
