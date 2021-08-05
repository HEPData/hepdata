.. _development:

***********
Development
***********

.. contents:: Table of Contents
    :depth: 3
    :local:


Basic Information
=================

HEPData is based on the `Invenio Framework <https://invenio.readthedocs.io/en/latest/index.html>`_  which in turn is
built using `Flask <https://flask.palletsprojects.com/en/1.1.x/>`_.

HEPData requires:

 * `PostgreSQL <http://www.postgresql.org/>`_ (version 9.6) databases
 * `Redis <http://redis.io/>`_ for caching
 * `Celery <https://docs.celeryproject.org/en/stable/index.html>`_ for managing asynchronous tasks
 * `Elasticsearch <https://www.elastic.co/products/elasticsearch>`_ for indexing and searching data

Useful links:

 * :ref:`Modules <modules>` contains API documentation on the modules/packages within the Flask app.
 * :ref:`CLI <cli>` gives details of the HEPData command line tools.


Other HEPData Repositories
==========================

This web application with repository
`HEPData/hepdata <https://github.com/HEPData/hepdata>`_ depends on some
other packages that can be found under the `@HEPData
<https://github.com/HEPData>`_ organization on GitHub.  These additional
repositories are necessary for
`validation <https://github.com/HEPData/hepdata-validator>`_,
`conversion <https://github.com/HEPData/hepdata-converter>`_,
and to provide the converter as a
`web service <https://github.com/HEPData/hepdata-converter-ws>`_ with a
`client wrapper <https://github.com/HEPData/hepdata-converter-ws-client>`_.
Further repositories build Docker images with the `converter
dependencies <https://github.com/HEPData/hepdata-converter-docker>`_ and
run the `converter web service
<https://github.com/HEPData/hepdata-converter-ws-docker>`_.  See `here
<https://github.com/HEPData/hepdata/wiki/Deployment#hepdata-converter>`_
for more details on how to deploy the conversion software in production.
The relation between these different packages is summarised in the
following diagram:

.. image:: HEPData-modules-3-2.png
  :alt: Other Repositories


JavaScript/Webpack
==================

Introduction
------------

The JavaScript and CSS are bundled using `Webpack <https://webpack.js.org>`_, via the following packages:

 * `pywebpack <https://pywebpack.readthedocs.io/en/latest/>`_ provides a way to define Webpack bundles in python.
 * `Flask-WebpackExt <https://flask-webpackext.readthedocs.io/en/latest/>`_ integrates `pywebpack` with Flask. It provides the `WebpackBundle` class used to define the entry points and contents of the Webpack packages, and the ``{{ webpack[...] }}`` template function used to inject javascript and css into a page.
 * `invenio-assets <https://invenio-assets.readthedocs.io/en/latest/>`_ integrates Flask-WebpackExt with Invenio and provides a CLI command to collect the assets.

Each module that requires javascript has a ``webpack.py`` file which list the JavaScript files and their dependencies. Dependencies need to be imported at the top of each JavaScript file.

Adding a new JavaScript file
----------------------------

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

Building JavaScript/CSS assets
------------------------------
To build all of the JavaScript, run:

.. code-block:: console

   (hepdata)$ hepdata webpack build

If you have made a change to a ``webpack.py`` file, run:

.. code-block:: console

   (hepdata)$ hepdata webpack buildall

Occasionally the Webpack build will complete but there will be errors higher up in the output. If the JavaScript file
does not load in the page (e.g. you see a ``KeyError: not in manifest.json`` error), check the webpack build output.

When making changes to the javascript you may find it helpful to build the javascript on-the-fly, which also builds in
development mode (so the generated JavaScript files are unminified and in separate files):

.. code-block:: console

   (hepdata)$ cd $HOME/.virtualenvs/hepdata/var/hepdata-instance/assets
   (hepdata)$ npm start


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


Single Sign On: Local development
=================================

CERN SSO
--------

Setting up a local app can be done via the `CERN Application Portal <https://application-portal.web.cern.ch>`_. (Ideally
you should use the `QA version of the portal <https://application-portal-qa.web.cern.ch>`_ but we have not yet succeeded
in setting that up - but see below for partial instructions.)

1. (QA only) Set up the CERN proxy following their `instructions <https://security.web.cern.ch/recommendations/en/ssh_browsing.shtml>`_.

2. Sign in to the `CERN Application Portal <https://application-portal.web.cern.ch>`_ (or the `CERN QA Application Portal <https://application-portal-qa.web.cern.ch>`_).

3. Click "Add an Application" and fill in the form:
    - Application Identifier: hepdata-local (example, must be globally unique)
    - Name: HEPData local installation
    - Home Page: https://hepdata.local (this doesn't affect the workings of the SSO but localhost is not allowed)
    - Description: Local installation of HEPData
    - Category: Personal

4. Once your application has been created, edit it and go to "SSO Registration", click the add (+) button, and fill in the form:
    - Select "OpenID Connect (OIDC)"
    - Redirect URI: https://localhost:5000/oauth/authorized/cern_openid/
    - Leave other boxes unchecked, submit and confirm.

5. You will be shown the Client ID and Client Secret. Copy these into ``config_local.py``:

   .. code-block:: python

       CERN_APP_OPENID_CREDENTIALS = dict(
           consumer_key="hepdata-local",
           consumer_secret="<your-client-secret>",
       )

6. Go to "Roles". Add a new Role:
    - Role Identifier: cern_user
    - Role Name: CERN user
    - Description: CERN user
    - Check "This role is required to access my application"
    - Check "This role applies to all authenticated users"
    - Leave the minimum level of assurance as it is.

7. If there is a default role, edit it and uncheck both "This role is required to access my application" and "This role applies to all authenticated users".

8. (QA only) Add the following settings to ``config_local.py``:

    .. code-block:: python

      from .config import CERN_REMOTE_APP
      CERN_REMOTE_APP['params']['base_url'] = "https://keycloak-qa.cern.ch/auth/realms/cern"
      CERN_REMOTE_APP['params']['access_token_url'] = "https://keycloak-qa.cern.ch/auth/realms/cern/protocol/openid-connect/token"
      CERN_REMOTE_APP['params']['authorize_url'] = "https://keycloak-qa.cern.ch/auth/realms/cern/protocol/openid-connect/auth"
      CERN_REMOTE_APP['logout_url'] = "https://keycloak-qa.cern.ch/auth/realms/cern/protocol/openid-connect/logout"
      OAUTHCLIENT_CERN_OPENID_USERINFO_URL = "https://keycloak-qa.cern.ch/auth/realms/cern/protocol/openid-connect/userinfo"

9. Run the hepdata app using an adhoc SSL certificate:

   .. code-block:: console

      (hepdata)$ pip install pyopenssl
      (hepdata)$ hepdata run --debugger --reload --cert=adhoc

10. Go to https://localhost:5000. You will see a warning that the connection is not private but choose "Advanced" and "Proceed to localhost (unsafe)" (or the equivalent in your browser).

11. Click "Sign in" and "Log in with CERN" and hopefully it will work as expected.


reCAPTCHA: Local development
============================
To use reCAPTCHA on your local ``register_user`` form, go to the `reCAPTCHA admin console <https://www.google.com/recaptcha/admin/>`_
(you will need a Google account) and add a new site with the following settings:

 - Label: **hepdata-local** (or another name of your choice)
 - reCAPTCHA type: choose **reCAPTCHA v2** and then **"I'm not a robot" Checkbox**
 - Domains: **localhost**

You will then be shown your reCAPTCHA keys, which you should set in ``config_local.py``:

.. code-block:: python

   RECAPTCHA_PUBLIC_KEY = "<Site Key>"
   RECAPTCHA_PRIVATE_KEY = "<Secret Key>"

The reCAPTCHA should now be visible on the signup form.

Adding CLI commands
===================
The :ref:`HEPData CLI <cli>` uses `click <https://click.palletsprojects.com/en/8.0.x/>`_ to define commands and
command groups. You can turn a function in ``cli.py`` into a new command by annotating it with ``@<group>.command()``
where ``<group>`` is the relevant command group, e.g. ``utils``.

You can call your new command via:

.. code-block:: console

   (hepdata)$ hepdata <group> <your-function-name-with-hyphens-not-underscores>

e.g. a method called ``my_fabulous_command`` annotated with ``@utils.command()`` could be called via:

.. code-block:: console

   (hepdata)$ hepdata utils my-fabulous-command

The `click docs <https://click.palletsprojects.com/en/8.0.x/>`_ give details of how to parse command-line arguments.


Fixing existing data
--------------------

Sometimes we need to make changes to data on HEPData.net, to fix issues caused by migrations or by previous
bugs, which are too complex to achieve with SQL or with simple python commands. The :ref:`HEPData CLI <cli>` has a
``fix`` group to be used in this situation, which uses code in the ``fixes`` directory, separate from the main HEPData
code.

To create a new ``fix`` command:

1. Create a new module file in ``fixes`` with an appropriate name.
2. Create a function to apply your fix, and annotate it with ``@fix.command()``.
