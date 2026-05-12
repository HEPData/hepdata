# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.
import os

from celery import shared_task
from datacite.errors import DataCiteUnauthorizedError, DataCiteError
from flask import render_template, current_app
from invenio_db import db
from invenio_pidstore.errors import PIDInvalidAction, PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier

from invenio_pidstore.providers.datacite import DataCiteProvider
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import xmlschema

from hepdata.modules.submission.models import DataSubmission, HEPSubmission, DataResource, License
from hepdata.modules.records.utils.common import get_record_by_id, generate_license_data_by_id
import logging

logging.basicConfig()
log = logging.getLogger(__name__)

# Cache the DataCite schema to avoid repeated downloads
_DATACITE_SCHEMA = None


def _get_datacite_schema():
    """Get cached DataCite schema or load it if not cached."""
    global _DATACITE_SCHEMA
    if _DATACITE_SCHEMA is None:
        try:
            _DATACITE_SCHEMA = xmlschema.XMLSchema('http://schema.datacite.org/meta/kernel-4.6/metadata.xsd')
        except Exception as e:
            log.error(f'Failed to load DataCite schema: {str(e)}', exc_info=True)
    return _DATACITE_SCHEMA


def _validate_datacite_xml(xml, doi):
    """
    Validate DataCite XML against the schema.
    
    :param xml: XML string to validate
    :param doi: DOI being registered (for logging purposes)
    :return: True if valid, False otherwise
    """
    schema = _get_datacite_schema()
    if schema is None:
        log.warning(f'DataCite schema not available, skipping validation for {doi}')
        return True
    
    try:
        schema.validate(xml)
        log.debug(f'DataCite XML validation passed for {doi}')
        return True
    except Exception as e:
        log.error(f'DataCite XML validation failed for {doi}: {str(e)}', exc_info=True)
        return False


class LicenseData:
    """Simple class to hold license data for template rendering"""
    def __init__(self, name, url, description):
        self.name = name
        self.url = url
        self.description = description


def get_license_for_datacite(license_id):
    """
    Get license data for DataCite XML generation.
    Returns a LicenseData object with either the specified license or default CC0.
    
    :param license_id: License ID or None
    :return: LicenseData object
    """
    if license_id:
        license_obj = License.query.filter_by(id=license_id).first()
        if license_obj and license_obj.name is not None:
            return LicenseData(license_obj.name, license_obj.url, license_obj.description)
    
    # Return default CC0 license data
    license_data = generate_license_data_by_id(None)
    return LicenseData(license_data['name'], license_data['url'], license_data['description'])


@shared_task
def generate_doi_for_table(doi):
    """
    Generate DOI for a specific table given by its doi.

    :param doi:
    :return:
    """

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')

    try:
        data_submission = DataSubmission.query.filter_by(doi=doi).one()
    except NoResultFound:
        print('Table DOI {} not found in database'.format(doi))
        return

    hep_submission = HEPSubmission.query.filter_by(
        inspire_id=data_submission.publication_inspire_id, version=data_submission.version, overall_status='finished'
    ).first()

    if hep_submission:
        create_data_doi.delay(hep_submission.id, data_submission.id, site_url)
    else:
        print('Finished submission with INSPIRE ID {} and version {} not found in database'.format(
            data_submission.publication_inspire_id, data_submission.version)
        )


@shared_task
def generate_dois_for_submission(*args, **kwargs):
    """
    Generate DOIs for all the submission components.

    :param args:
    :param kwargs:
    :return:
    """

    site_url = current_app.config.get('SITE_URL', 'https://www.hepdata.net')
    hep_submissions = HEPSubmission.query.filter_by(**kwargs).order_by(HEPSubmission.publication_recid.asc()).all()

    for hep_submission in hep_submissions:

        if args:
            start_recid, end_recid = args
            if hep_submission.publication_recid < start_recid or hep_submission.publication_recid > end_recid:
                continue

        if hep_submission.overall_status != 'finished':
            continue

        data_submissions = DataSubmission.query.filter_by(publication_inspire_id=hep_submission.inspire_id,
                                                          version=hep_submission.version).order_by(
            DataSubmission.id.asc())

        file_resources = _get_submission_file_resources(
            hep_submission.publication_recid, hep_submission.version,
            hep_submission)

        if hep_submission.doi is None:
            reserve_doi_for_hepsubmission(hep_submission)

        if any(d.doi is None for d in data_submissions):
            reserve_dois_for_data_submissions(data_submissions=data_submissions)

        if any(r.doi is None for r in file_resources):
            reserve_dois_for_resources(publication_recid=hep_submission.publication_recid,
                                       version=hep_submission.version,
                                       resources=file_resources)

        create_container_doi.delay(hep_submission.id,
                                   [d.id for d in data_submissions],
                                   [r.id for r in file_resources],
                                   site_url)

        for data_submission in data_submissions:
            create_data_doi.delay(hep_submission.id, data_submission.id, site_url)

        for resource in file_resources:
            create_resource_doi.delay(hep_submission.id, resource.id, site_url)


@shared_task(max_retries=6, default_retry_delay=10 * 60)
def create_container_doi(hep_submission_id, data_submission_ids, resource_ids, site_url):
    """
    Creates the payload to wrap the whole submission.

    :param hep_submission:
    :param data_submissions:
    :param resource_ids:
    :param publication_info:
    :return:
    """
    hep_submission = db.session.query(HEPSubmission).get(hep_submission_id)
    data_submissions = db.session.query(DataSubmission).filter(
        DataSubmission.id.in_(data_submission_ids)
    ).all()
    resources = db.session.query(DataResource).filter(
        DataResource.id.in_(resource_ids)
    ).all()

    publication_info = get_record_by_id(hep_submission.publication_recid)
    version_doi = hep_submission.doi + ".v{0}".format(hep_submission.version)

    # Get all versions for this publication (for unversioned DOI to include all versions)
    all_versions = db.session.query(HEPSubmission).filter(
        HEPSubmission.publication_recid == hep_submission.publication_recid,
        HEPSubmission.overall_status == 'finished'
    ).order_by(HEPSubmission.version.asc()).all()

    base_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                               doi=hep_submission.doi,
                               overall_submission=hep_submission,
                               data_submissions=data_submissions,
                               resources=resources,
                               all_versions=all_versions,
                               publication_info=publication_info,
                               site_url=site_url)

    # Validate the XML against DataCite schema
    _validate_datacite_xml(base_xml, hep_submission.doi)

    version_xml = render_template('hepdata_records/formats/datacite/datacite_container_submission.xml',
                                  doi=version_doi,
                                  overall_submission=hep_submission,
                                  data_submissions=data_submissions,
                                  resources=resources,
                                  all_versions=all_versions,
                                  publication_info=publication_info,
                                  site_url=site_url)

    # Validate the XML against DataCite schema
    _validate_datacite_xml(version_xml, version_doi)

    # Register DOI for the version, and update the base DOI to resolve to the latest submission version.
    register_doi(hep_submission.doi, site_url + '/record/ins{0}'.format(publication_info['inspire_id']),
                 base_xml, publication_info['uuid'])

    register_doi(version_doi, site_url + '/record/ins{0}?version={1}'.format(
        publication_info['inspire_id'], hep_submission.version), version_xml, publication_info['uuid'])


@shared_task(max_retries=6, default_retry_delay=10 * 60)
def create_data_doi(hep_submission_id, data_submission_id, site_url):
    """
    Generate DOI record for a data record.

    :param data_submission_id:
    :param version:
    :return:
    """
    hep_submission = db.session.query(HEPSubmission).get(hep_submission_id)
    data_submission = db.session.query(DataSubmission).get(data_submission_id)

    data_file = DataResource.query.filter_by(id=data_submission.data_file).first()
    publication_info = get_record_by_id(hep_submission.publication_recid)

    # Always provide license data - either from the data file or default CC0
    license_id = None
    if data_file and data_file.file_license:
        license_id = data_file.file_license
    license = get_license_for_datacite(license_id)

    xml = render_template('hepdata_records/formats/datacite/datacite_data_record.xml',
                          doi=data_submission.doi,
                          table_name=data_submission.name,
                          table_description=data_submission.description,
                          overall_submission=hep_submission,
                          data_submission=data_submission,
                          license=license,
                          publication_info=publication_info,
                          site_url=site_url)

    # Validate the XML against DataCite schema
    _validate_datacite_xml(xml, data_submission.doi)

    register_doi(data_submission.doi,
                 site_url + '/record/{0}'.format(data_submission.associated_recid),
                 xml, publication_info['uuid'])


@shared_task(max_retries=6, default_retry_delay=10 * 60)
def create_resource_doi(hep_submission_id, resource_id, site_url):
    """
    Generate DOI record for a data resource

    :param resource_id:
    :param version:
    :return:
    """
    hep_submission = db.session.query(HEPSubmission).get(hep_submission_id)
    resource = db.session.query(DataResource).get(resource_id)
    publication_info = get_record_by_id(hep_submission.publication_recid)

    # Always provide license data - either from the resource or default CC0
    license = get_license_for_datacite(resource.file_license)

    xml = render_template(
        'hepdata_records/formats/datacite/datacite_resource.xml',
        resource=resource,
        doi=resource.doi,
        overall_submission=hep_submission,
        filename=os.path.basename(resource.file_location),
        license=license,
        publication_info=publication_info,
        site_url=site_url
    )

    # Validate the XML against DataCite schema
    _validate_datacite_xml(xml, resource.doi)

    register_doi(
        resource.doi,
        site_url + '/record/resource/{0}?landing_page=true'.format(resource.id),
        xml,
        publication_info['uuid']
    )


def reserve_doi_for_hepsubmission(hepsubmission, update=False):
    base_doi = "{0}/hepdata.{1}".format(
        current_app.config.get('DOI_PREFIX'), hepsubmission.publication_recid)

    version = hepsubmission.version
    if version == 0:
        version += 1

    if hepsubmission.doi is None:
        get_or_create_doi(base_doi)
        hepsubmission.doi = base_doi
        db.session.add(hepsubmission)
        db.session.commit()

    if not update:
        get_or_create_doi(base_doi + ".v{0}".format(version))


def reserve_dois_for_data_submissions(*args, **kwargs):
    """
    Reserves a DOI for a data submission and saves to the datasubmission object.

    :param data_submission: DataSubmission object representing a data table.
    :return:
    """

    if kwargs.get('data_submissions'):
        data_submissions = kwargs.get('data_submissions')
    elif kwargs.get('publication_inspire_id') or kwargs.get('publication_recid'):
        data_submissions = DataSubmission.query.filter_by(**kwargs).order_by(DataSubmission.id.asc())
    else:
        raise KeyError('No inspire_id or data_submissions parameter provided')

    for index, data_submission in enumerate(data_submissions):
        # using the index of the sorted submissions should do a good job of maintaining the order of the tables.
        version = data_submission.version
        if version == 0:
            version += 1

        doi_value = "{0}/hepdata.{1}.v{2}/t{3}".format(
            current_app.config.get('DOI_PREFIX'), data_submission.publication_recid, version, (index + 1))

        if data_submission.doi is None:
            get_or_create_doi(doi_value)
            data_submission.doi = doi_value
            db.session.add(data_submission)

    db.session.commit()


def reserve_dois_for_resources(publication_recid, version, resources=None):
    """
    Reserves a DOI for a data submission and saves to the datasubmission object.

    :param resources: list of DataResource objects
    :return:
    """
    if not resources:
        resources = _get_submission_file_resources(publication_recid, version)

    for index, resource in enumerate(resources):
        # using the index of the sorted resources should do a good job of maintaining the order of the tables.
        if version == 0:
            version += 1

        doi_value = "{0}/hepdata.{1}.v{2}/r{3}".format(
            current_app.config.get('DOI_PREFIX'), publication_recid, version, (index + 1))

        if resource.doi is None:
            get_or_create_doi(doi_value)
            resource.doi = doi_value
            db.session.add(resource)

    db.session.commit()


def get_or_create_doi(doi):
    """
    :param doi: Creates a DOI using the data provider. If it already exists, we return back the existing provider.
    :return: DataCiteProvider
    """
    if current_app.config.get('NO_DOI_MINTING', False): # pragma: no cover
        log.info(f"Would create DOI {doi}")
        return None

    try:
        # Check if DOI already exists and return
        return DataCiteProvider.get(doi, 'doi')
    except PIDDoesNotExistError:
        # DOI does not exist so create it
        try:
            return DataCiteProvider.create(doi)
        except Exception as e:
            log.error(f'Unable to mint DOI: {str(e)}', exc_info=True)
    except Exception as e:
        log.error(f'Unable to fetch DOI: {str(e)}', exc_info=True)


def register_doi(doi, url, xml, uuid):
    """
    Given a data submission id, this method takes its assigned DOI, creates the DataCite XML,
    and registers the DOI.

    :param data_submissions:
    :param recid:
    :return:
    """
    if current_app.config.get('NO_DOI_MINTING', False) or not doi: # pragma: no cover
        log.info(f"Would mint DOI {doi}")
        return None

    log.info('{0} - {1}'.format(doi, url))

    print('Minting doi {}'.format(doi))
    provider = get_or_create_doi(doi)

    pidstore_obj = PersistentIdentifier.query.filter_by(pid_value=doi).first()
    if pidstore_obj:
        pidstore_obj.object_uuid = uuid
        db.session.add(pidstore_obj)
        db.session.commit()
    try:
        provider.register(url, xml)
    except DataCiteUnauthorizedError:
        log.error('Unable to mint DOI. No authorisation credentials provided.')
    except (PIDInvalidAction, IntegrityError):
        try:
            provider.update(url, xml)  # try again in case of temporary problem
        except DataCiteError:
            try:
                provider.update(url, xml)
            except DataCiteError as dce:
                log.error('Error updating {0} for URL {1}\n\n{2}'.format(doi, url, dce))
    except DataCiteError:
        try:
            provider.register(url, xml)  # try again in case of temporary problem
        except (PIDInvalidAction, IntegrityError):
            try:
                provider.update(url, xml)
            except DataCiteError as dce:
                log.error('Error updating {0} for URL {1}\n\n{2}'.format(doi, url, dce))
        except DataCiteError as dce:
            log.error('Error registering {0} for URL {1}\n\n{2}'.format(doi, url, dce))


def _get_submission_file_resources(recid, version, submission=None):
    """
    Gets a list of resources for a publication, relevant to all data records.

    :param recid:
    :param version:
    :return: list of DataResource objects
    """
    if submission is None:
        submission = HEPSubmission.query.filter_by(publication_recid=recid, version=version).first()

    file_resources = [
        r for r in submission.resources if not r.file_location.lower().startswith('http')
    ]
    file_resources.sort(key=lambda r: r.id)
    return file_resources
