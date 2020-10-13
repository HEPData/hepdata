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

"""Functions for parsing the new INSPIRE JSON metadata."""

from copy import deepcopy

parsed_content_defaults = {
    'title': None,
    'doi': None,
    'authors': None,
    'type': [],
    'abstract': 'None',
    'creation_date': None,
    'arxiv_id': None,
    'collaborations': [],
    'keywords': [],
    'journal_info': 'No Journal Information',
    'year': None,
    'subject_area': [],
}


def get_title(metadata):
    """Get the title of the publication from the first value in list of english translations (if applicable) otherwise from first title in list of titles."""
    title = deepcopy(parsed_content_defaults['title'])
    if 'title_translations' in metadata.keys():
        for title_translation in metadata['title_translations']:
            if title_translation['language'] == 'en':
                title = title_translation['title']
    if title is parsed_content_defaults['title'] and 'titles' in metadata.keys() and len(metadata['titles']) > 0:
        title = metadata['titles'][0]['title']
    return title


def get_doi(metadata):
    """Get the DOI of the journal publication from the first value in the list of DOIs."""
    doi = deepcopy(parsed_content_defaults['doi'])
    if 'dois' in metadata and len(metadata['dois']) > 0:
        doi = metadata['dois'][0]['value']
    return doi


def get_authors(metadata):
    """Get the authors of the publication as a list of dictionaries with keys 'affiliation' and 'full_name'."""
    authors = deepcopy(parsed_content_defaults['authors'])
    if 'authors' in metadata.keys():
        authors = [{'affiliation': (author['affiliations'][0]['value'] if 'affiliations' in author.keys() else ''),
                    'full_name': author['full_name']}
                   for author in metadata['authors']]
    return authors


def get_type(metadata):
    """Get the type of the publication"""
    _type = deepcopy(parsed_content_defaults['type'])
    if 'document_type' in metadata.keys():
        _type = metadata['document_type']
    return _type


def get_abstract(metadata):
    """Get the abstract of the publication, ideally the one from the arXiv version, otherwise the first one."""
    abstract = deepcopy(parsed_content_defaults['abstract'])
    if 'abstracts' in metadata.keys():
        abstract = metadata['abstracts'][0]['value']
        for _abstract in metadata['abstracts']:
            if 'value' in _abstract.keys() and 'source' in _abstract.keys() and _abstract['source'] == 'arXiv':
                abstract = _abstract['value']
    return abstract


def get_creation_date(metadata):
    """Get the creation date of the publication, first try to expand the preprint_date, otherwise try legacy_creation_date."""
    creation_date = deepcopy(parsed_content_defaults['creation_date'])
    if 'preprint_date' in metadata.keys():
        creation_date = expand_date(metadata['preprint_date'])
    elif 'legacy_creation_date' in metadata:
        creation_date = metadata['legacy_creation_date']
    return creation_date


def get_arxiv_id(metadata):
    """Get the arxiv id of the publication from the last value in the list of arxiv eprints."""
    arxiv_id = deepcopy(parsed_content_defaults['arxiv_id'])
    if 'arxiv_eprints' in metadata.keys():
        arxiv_id = 'arXiv:' + metadata['arxiv_eprints'][-1]['value']
    return arxiv_id


def get_collaborations(metadata):
    """Get the collaborations of the publication as a list."""
    collaborations = deepcopy(parsed_content_defaults['collaborations'])
    if 'collaborations' in metadata:
        collaborations = [collaboration['value'] for collaboration in metadata['collaborations']]
    return collaborations


def get_keywords(metadata):
    """Get the keywords of the publication."""
    keywords = deepcopy(parsed_content_defaults['keywords'])
    if 'keywords' in metadata.keys():
        keywords = metadata['keywords']
    return keywords


def get_journal_info(metadata):
    """
    Get the journal information of the publication. Format is 'title volume (year) article page_start-page_end' if at least one of these information is available,
    otherwise attempt to obtain it from 'pubinfo_freetext' or 'publication_info' or 'report_numbers' or 'public_notes'. Defaults to 'No Journal Information'.
    """
    default_journal_info, journal_info = deepcopy(parsed_content_defaults['journal_info']), ''
    if 'publication_info' in metadata:
        if 'journal_title' in metadata['publication_info'][0].keys():
            journal_info += metadata['publication_info'][0]['journal_title'] + ' '
        if 'journal_volume' in metadata['publication_info'][0].keys():
            journal_info += metadata['publication_info'][0]['journal_volume'] + ' '
        if 'year' in metadata['publication_info'][0].keys():
            journal_info += '(' + str(metadata['publication_info'][0]['year']) + ') '
        if 'artid' in metadata['publication_info'][0].keys():
            journal_info += metadata['publication_info'][0]['artid'] + ' '
        if 'page_start' in metadata['publication_info'][0].keys() and 'page_end' in metadata['publication_info'][0].keys():
            journal_info += metadata['publication_info'][0]['page_start'] + "-" + metadata['publication_info'][0]['page_end']
        if journal_info != '':
            journal_info = journal_info.strip()  # trim to remove whitespace
            return journal_info
    if ('publication_info' in metadata and len(metadata['publication_info']) > 0 and type(metadata['publication_info'][0]) is dict and
       'pubinfo_freetext' in metadata['publication_info'][0].keys()):
        journal_info = metadata['publication_info'][0]['pubinfo_freetext']
    elif 'report_numbers' in metadata and len(metadata['report_numbers']) > 0:
        journal_info = metadata['report_numbers'][0]['value']
    elif ('public_notes' in metadata.keys() and any(['value' in public_note.keys() and "Submitted to " in public_note['value'] for public_note in metadata['public_notes']])):
        journal_info = [public_note['value'].replace("Submitted to ", "") for public_note in metadata['public_notes'] if
                        ('value' in public_note.keys() and "Submitted to " in public_note['value'])][0]
    if '. All figures' in journal_info:
        journal_info = journal_info.replace('. All figures', '')
    if journal_info != '':
        return journal_info
    else:
        return default_journal_info


def get_year(metadata):
    """Get the year of the publication. Try first 'imprints/date', then 'publication_info/year', then 'preprint_date', and finally 'legacy_creation_date'."""
    year = deepcopy(parsed_content_defaults['year'])
    if 'imprints' in metadata.keys() and any(['date' in imprint.keys() and len(imprint['date']) == 4 for imprint in metadata['imprints']]):
        year = [imprint['date'] for imprint in metadata['imprints'] if 'date' in imprint.keys() and len(imprint['date']) == 4][0]
    elif ('publication_info' in metadata and 'year' in metadata['publication_info'][0].keys()):
        year = str(metadata['publication_info'][0]['year'])
    elif 'preprint_date' in metadata.keys():
        year = metadata['preprint_date'].split("-")[0]
    elif 'legacy_creation_date' in metadata:
        year = metadata['legacy_creation_date'].split("-")[0]
    return year


def get_subject_area(metadata):
    subject_area = deepcopy(parsed_content_defaults['subject_area'])
    if 'arxiv_eprints' in metadata.keys():
        subject_area += metadata['arxiv_eprints'][-1]['categories']
    if ('inspire_categories' in metadata.keys() and len(metadata['inspire_categories']) > 0):
        subject_area += [entry['term'].replace('Experiment-HEP', 'hep-ex').replace('Experiment-Nucl', 'nucl-ex').replace('Theory-Nucl', 'nucl-th') for
                         entry in metadata['inspire_categories'] if 'term' in entry.keys() and entry['term'] != 'Other']
    subject_area = list(set(subject_area))
    return subject_area


def updated_parsed_content_for_thesis(content, parsed_content):
    parsed_content['dissertation'] = content['metadata']['thesis_info']
    # fix dissertation/institutions -> dissertation/institution if there is only one
    if ('institutions' in parsed_content['dissertation'].keys() and
       len(parsed_content['dissertation']['institutions']) == 1 and
       'name' in parsed_content['dissertation']['institutions'][0]):
        parsed_content['dissertation']['institution'] = parsed_content['dissertation']['institutions'][0]['name']
        parsed_content['dissertation'].pop('institutions')
    # update year with thesis info
    if 'date' in content['metadata']['thesis_info'].keys():
        parsed_content['year'] = content['metadata']['thesis_info']['date']
        if parsed_content['year'] is not None:
            if content['metadata']['legacy_creation_date'][:4] == parsed_content['year']:
                parsed_content['creation_date'] = content['metadata']['legacy_creation_date']
            else:
                parsed_content['creation_date'] = expand_date(parsed_content['year'])
    # fix capitals in dissertation/type
    if 'degree_type' in parsed_content['dissertation'].keys():
        parsed_content['dissertation']['type'] = parsed_content['dissertation'].pop('degree_type').title()
        if parsed_content['dissertation']['type'] == "Phd":
            parsed_content['dissertation']['type'] = "PhD"
    # fix dissertation/defence_date string
    if 'date' in parsed_content['dissertation'].keys():
        parsed_content['dissertation']['defense_date'] = parsed_content['dissertation'].pop('date')
    return parsed_content


def expand_date(value):
    """
    In the case where the date is not completely
    formed, we need to expand it out.
    so 2012-08 will be 2012-08-01
    and 2012 will be 2012-01-01.
    If nothing, we do nothing.

    :param value:
    :return:
    """
    if value == '':
        return value

    date_parts = value.split('-')

    if len(date_parts) == 1:
        date_parts.append('01')
    if len(date_parts) == 2:
        date_parts.append('01')
    return "-".join(date_parts)
