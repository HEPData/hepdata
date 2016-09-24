# -*- coding: utf-8 -*-
#
# This file is part of hepdata.
# Copyright (C) 2015 CERN.
#
# hepdata is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# hepdata is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with hepdata; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""hepdata - Research. Shared."""

import os
import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

readme = open('README.rst').read()
history = open('CHANGES.rst').read()

tests_require = [
    'check-manifest>=0.25',
    'coverage>=4.0',
    'isort>=4.2.2',
    'mock>=1.3.0',
    'pydocstyle>=1.0.0',
    'pytest-cache>=1.0',
    'pytest-cov>=1.8.0',
    'pytest-flask>=0.10.0',
    'pytest-pep8>=1.0.6',
    'pytest>=2.8.0',
    # 2.53.0 introduced a Python 3 compatibility issue. Wait for it to be fixed
    'selenium>=2.48.0,<2.53.0',
    'six>=1.10.0'

]

extras_require = {'docs': [
    'Sphinx>=1.3',
], 'postgresql': [
    'invenio-db[postgresql]>=1.0.0a6',
], 'mysql': [
    'invenio-db[mysql]>=1.0.0a6',
], 'sqlite': [
    'invenio-db>=1.0.0a6',
], 'tests': tests_require, 'all': []}

for name, reqs in extras_require.items():
    if name in ('postgresql', 'mysql', 'sqlite'):
        continue
    extras_require['all'].extend(reqs)

setup_requires = [
    'Babel>=1.3',
]

install_requires = [
    # 'invenio-search-ui',
    'Flask>=0.11.1',
    'Flask-CLI>=0.4.0',
    'Flask-BabelEx>=0.9.2',
    'Flask-Debugtoolbar>=0.10.0',
    'idutils>=0.1.1',
    'raven<=5.1.0',
    'invenio-access',
    'invenio-accounts',
    'invenio-admin',
    'invenio-assets>=1.0.0b2',
    'invenio-base>=1.0.0a11',
    'invenio-celery',
    'invenio-config',
    'invenio-i18n',
    'invenio-logging',
    'invenio-mail',
    'invenio-pidstore',
    'invenio-records',
    'invenio-search',
    'invenio-theme',
    'invenio-oauth2server>=1.0.0a5',
    'invenio-oauthclient>=1.0.0a6',
    'invenio-userprofiles',
    'invenio>=3.0.0a1,<3.1.0',
    'jsonref',
    'flask-cors',
    'timestring',
    'cryptography',
    'beautifulsoup4',
    'hepdata_validator==0.1.10',
    'hepdata-converter-ws-client',
    'datacite'
]

packages = find_packages()


class PyTest(TestCommand):
    """PyTest Test."""

    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        """Init pytest."""
        TestCommand.initialize_options(self)
        self.pytest_args = []
        try:
            from ConfigParser import ConfigParser
        except ImportError:
            from configparser import ConfigParser
        config = ConfigParser()
        config.read('pytest.ini')
        self.pytest_args = config.get('pytest', 'addopts').split(' ')

    def finalize_options(self):
        """Finalize pytest."""
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        """Run tests."""
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join('hepdata', 'version.py'), 'rt') as fp:
    exec (fp.read(), g)
    version = g['__version__']

setup(
    name='hepdata',
    version=version,
    description=__doc__,
    long_description=readme + '\n\n' + history,
    keywords='hepdata research data repository',
    license='GPLv2',
    author='CERN',
    author_email='info@hepdata.net',
    url='https://github.com/hepdata/hepdata',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'console_scripts': [
            'hepdata = hepdata.cli:cli'
        ],
        'invenio_base.apps': [
            'hepdata_records = hepdata.modules.records.ext:HEPDataRecords'
        ],

        'invenio_db.models': [
            'hepdata_submissions = hepdata.modules.submission.models',
            'hepdata_stats = hepdata.modules.stats.models',
            'hepdata_subscribers = hepdata.modules.records.subscribers.models',
            'hepdata_permissions = hepdata.modules.permissions.models'

        ],
        'invenio_base.blueprints': [
            'hepdata_theme = hepdata.modules.theme.views:blueprint',
            'hepdata_dashboard = hepdata.modules.dashboard.views:blueprint',
            'hepdata_search = hepdata.modules.search.views:blueprint',
            'hepdata_submission = hepdata.modules.submission.views:blueprint',
            'inspire_api = hepdata.modules.inspire_api.views:blueprint',
            'hepdata_conversion = hepdata.modules.converter.views:blueprint',
            'hepdata_subscriptions = hepdata.modules.records.subscribers.rest:blueprint',
            'hepdata_permissions = hepdata.modules.permissions.views:blueprint'
        ],
        'invenio_celery.tasks': [
            'hepdata_records = hepdata.modules.records.migrator.api',
            'hepdata_doi = hepdata.modules.records.utils.doi_minter',
            'hepdata_mail = hepdata.utils.mail',
        ],
        'invenio_i18n.translations': [
            'messages = hepdata',
        ],
        'invenio_assets.bundles': [
            'hepdata_theme_css = hepdata.modules.theme.bundles:css',
            'hepdata_info_page_css = hepdata.modules.theme.bundles:info_page_css',
            'hepdata_bootstrap_js = hepdata.modules.theme.bundles:bootstrap_js',
            'hepdata_submission_js = hepdata.modules.submission.bundles:submission_js',
            'hepdata_search_js = hepdata.modules.search.bundles:search_js',
            'hepdata_record_js = hepdata.modules.records.bundles:record_js',
            'hepdata_vis_js = hepdata.modules.records.bundles:vis_js',
            'hepdata_dashboard_js = hepdata.modules.dashboard.bundles:dashboard_js',

            'hepdata_record_css = hepdata.modules.theme.bundles:record_css',
            'hepdata_search_css = hepdata.modules.theme.bundles:search_css',
        ],
        'invenio_admin.views': [
            'hepdata_submission_view = hepdata.modules.submission.admin:hep_submission_admin_view',
            'hepdata_participant_view = hepdata.modules.permissions.admin:hep_participant_admin_view',
            'hepdata_coordinator_request_view = hepdata.modules.permissions.admin:coordinator_request_admin_view',
            'hepdata_dataresource_view = hepdata.modules.submission.admin:hep_dataresource_admin_view'
        ]
    },
    extras_require=extras_require,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Development Status :: Production',
    ],
    cmdclass={'test': PyTest},
)
