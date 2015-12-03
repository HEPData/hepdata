Installation
============

First install Zenodo all requirements:

.. code-block:: console

   $ mkvirtualenv zenodo3
   (zenodo3)$ pip install -r requirements.txt --pre --src ~/src/ --exists-action i
   (zenodo3)$ pip install -e .[postgresql]


Next, install and build assets:

.. code-block:: console

   (zenodo3)$ zenodo npm
   (zenodo3)$ cdvirtualenv var/zenodo-instance/static
   (zenodo3)$ npm install
   (zenodo3)$ zenodo collect -v
   (zenodo3)$ zenodo assets build


Next, create the database and database tables if you haven't already done so:

.. code-block:: console

   (zenodo3)$ zenodo db init
   (zenodo3)$ zenodo db create

Now, start Zenodo:

   (zenodo3)$ zenodo --debug run
