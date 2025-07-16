# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2020 CERN.
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

from setuptools import find_packages, setup

readme = open('README.rst').read()
history = open('CHANGES.rst').read()

tests_require = [
    'pytest>=6.0.2,<8.0.0',  # see https://github.com/HEPData/hepdata/issues/815
    'pytest-cov>=2.9.0,<4.0.0',  # see https://github.com/HEPData/hepdata/issues/580
    'pytest-flask>=1.0.0',
    'pytest-mock>=3.1.0',
    'pytest-timeout>=1.4.2',
    'requests-mock>=1.8.0',
    'selenium>=4.0.0',
    'xmlschema>=4.0.0'
]

extras_require = {
    'all': [],
    'docs': [
        'Sphinx>=1.8.5,!=3.4.2',
        'sphinx-click>=2.1.0',
    ],
    'tests': tests_require,
}

for name, reqs in extras_require.items():
    extras_require['all'].extend(reqs)

# Packages moved to requirements.txt with specific versions
install_requires = []

packages = find_packages()

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
    url='https://github.com/HEPData/hepdata',
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
            'hepdata_permissions = hepdata.modules.permissions.views:blueprint',
            'hepdata_doibanner = hepdata.modules.doi_banner.views:blueprint'
        ],
        'invenio_celery.tasks': [
            'hepdata_analyses = hepdata.modules.records.utils.analyses',
            'hepdata_importer = hepdata.modules.records.importer.api',
            'hepdata_doi = hepdata.modules.records.utils.doi_minter',
            'hepdata_mail = hepdata.modules.email.utils',
            'hepdata_conversion = hepdata.modules.converter.tasks',
            'hepdata_opensearch = hepdata.ext.opensearch.api',
            'hepdata_inspireupdate = hepdata.modules.records.utils.records_update_utils',
            'hepdata_delete = hepdata.modules.records.utils.submission'
        ],
        'invenio_i18n.translations': [
            'messages = hepdata',
        ],
        'invenio_assets.webpack': [
            'hepdata_theme_css = hepdata.modules.theme.webpack:theme',
            'hepdata_submission_js = hepdata.modules.submission.webpack:submission_js',
            'hepdata_search_js = hepdata.modules.search.webpack:search_js',
            'hepdata_record_js = hepdata.modules.records.webpack:record_js',
            'hepdata_dashboard_js = hepdata.modules.dashboard.webpack:dashboard_js',
        ],
        'invenio_admin.views': [
            'hepdata_participant_view = hepdata.modules.permissions.admin:hep_participant_admin_view',
            'hepdata_coordinator_request_view = hepdata.modules.permissions.admin:coordinator_request_admin_view',
            'hepdata_dataresource_view = hepdata.modules.submission.admin:hep_dataresource_admin_view',
        ]
    },
    extras_require=extras_require,
    install_requires=install_requires,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Development Status :: Production',
    ],
    python_requires='>=3.9, <3.10',
)
