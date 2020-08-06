# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Functions for parsing the old INSPIRE MARCXML metadata."""

from dateutil.parser import parse

marc_tags = {
    'title': ('245', 'a'),
    'title_translation': ('242', 'a'),
    'abstract': ('520', 'a'),
    'doi': ('024', '7', 'a', '2'),
    'first_author': ('100', 'a', 'u'),
    'coauthors': ('700', 'a', 'u'),
    'arxiv': ('037', '9', 'a'),
    'collaboration': ('710', 'g'),
    'keywords': ('695', 'a'),
    'date': ('269', 'c'),
    'collection': ('980', 'a'),
    'year': ('260', 'c'),
    'journal': ('773', ['p', 'v', 'y', 'c']),
    'dissertation_note': ('502', 'b', 'c', 'd'),
    'subject_area': ('650', 'a')
}

DEFAULT_JOURNAL = 'No Journal Information'


def get_journal_info(soup):
    """Parse the journal information from the xml."""
    try:
        tag, codes = marc_tags['journal']
        datafield = soup.find_all(tag=tag)[0]
        journal_info = ''
        year = None

        for code in codes:
            if datafield.find_all(code=code):
                value = datafield.find_all(code=code)[0].string
                if code == 'y':
                    year = value
                    value = '(' + value + ')'
                journal_info += value + ' '

        return journal_info[:-1], year
    except Exception:
        return DEFAULT_JOURNAL, None


def get_year(soup):
    try:
        tag, code = marc_tags['year']
        datafield = soup.find_all(tag=tag)[0]
        return parse(datafield.find_all(code=code)[0].string).year
    except:
        return None


def get_doi(soup):
    """Parse the DOI from the xml."""
    try:
        (tag, ind1, code1, code2) = marc_tags['doi']
        datafields = soup.find_all(tag=tag, ind1=ind1)
        for datafield in datafields:
            if datafield.find_all(code=code1) and datafield.find_all(code=code2):
                assert datafield.find_all(code=code2)[0].string.lower() == 'doi'
                return datafield.find_all(code=code1)[0].string
        return None
    except (IndexError, AssertionError):
        return None


def get_title(soup):
    """Parse the title from the xml.  Use translated title if present."""
    for title in ['title_translation', 'title']:
        try:
            (tag, code) = marc_tags[title]
            datafield = soup.find_all(tag=tag)[0]
            return datafield.find_all(code=code)[0].string
        except IndexError:
            pass
    return None


def get_authors(soup):
    """Parse the authors from the xml."""
    try:
        (tag, code_name, code_aff) = marc_tags['first_author']
        datafield = soup.find_all(tag=tag)[0]
        authors = [get_author_from_subfield(datafield, code_name, code_aff)]

        (tag, code_name, code_aff) = marc_tags['coauthors']
        datafields = soup.find_all(tag=tag)
        for df in datafields:
            coauthor = get_author_from_subfield(df, code_name, code_aff)
            authors.append(coauthor)

        return authors
    except IndexError:
        return None


def get_abstract(soup):
    """Parse the abstract from the xml."""
    try:
        (tag, code) = marc_tags['abstract']
        datafield = soup.find_all(tag=tag)[0]
        return datafield.find_all(code=code)[0].string
    except IndexError:
        return None


def get_arxiv(soup):
    """Parse the arxiv ID from the xml."""
    (tag, code1, code2) = marc_tags['arxiv']
    for df in soup.find_all(tag=tag):
        subfield = df.find_all(code=code1)
        if subfield != [] and subfield[0].string == 'arXiv':
            try:
                return df.find_all(code=code2)[0].string
            except IndexError:
                return None

    return None


def get_collaborations(soup):
    """Parse the collaboration names from the xml."""
    (tag, code) = marc_tags['collaboration']
    datafields = soup.find_all(tag=tag)
    return [df.find_all(code=code)[0].string for df in datafields
            if df.find_all(code=code)]


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
    if value is '':
        return value

    date_parts = value.split('-')

    if len(date_parts) == 1:
        date_parts.append('01')
    if len(date_parts) == 2:
        date_parts.append('01')
    return "-".join(date_parts)


def get_date(soup):
    """Parse the date from the xml."""
    try:
        (tag, code) = marc_tags['date']
        datafields = soup.find_all(tag=tag)
        for datafield in datafields:
            if datafield.find_all(code=code):
                value = datafield.find_all(code=code)[0].string
                date = expand_date(value)
                return date, parse(date).year
        return None, None
    except IndexError:
        return None, None


def get_author_from_subfield(datafield, code_name, code_aff):
    """Dig out the author from xml subfield."""
    author = datafield.find_all(code=code_name)[0].string
    university = datafield.find_all(code=code_aff)
    university = university[0].string if university else ''
    return {'full_name': author, 'affiliation': university}


def get_keywords(soup):
    """Parse the keywords from the xml."""
    (tag, code) = marc_tags['keywords']
    datafields = soup.find_all(tag=tag)
    keywords = [df.find_all(code=code)[0].string for df in datafields
                if df.find_all(code=code)]
    return make_keyword_dicts(keywords)


def get_collection(soup, marc_tag='collection'):
    """Finds the 980 code relating to thesis type."""
    (tag, code) = marc_tags[marc_tag]
    datafields = soup.find_all(tag=tag)
    collections = [df.find_all(code=code)[0].string for df in datafields if df.find_all(code=code)]
    collections = filter(lambda x: x is not None, collections)
    collections = list(map(lambda x: x.lower(), collections))
    return collections


def get_subject_areas(soup):
    subject_areas = get_collection(soup, marc_tag='subject_area')

    filtered = []
    for subject_area in subject_areas:
        if 'experiment' in subject_area or subject_area == 'hep-ex':
            filtered.append('HEP Experiment')
        elif 'theory' in subject_area or subject_area == 'hep-th':
            filtered.append('HEP Theory')

    return list(set(filtered))


def get_dissertation(soup):
    (tag, diploma_type, institution, date) = marc_tags['dissertation_note']
    datafield = soup.find(tag=tag)
    if datafield is None:
        return {}

    type = datafield.find(code=diploma_type).string
    university = datafield.find(code=institution).string
    defense_date = datafield.find(code=date).string
    return {'type': type, 'institution': university, 'defense_date': defense_date}


def make_keyword_dicts(keywords):
    """Map the list of keyword strings into dictionaries containing name, value and synonyms fields."""
    kw_dicts = []
    for kw in keywords:
        if ':' in kw:
            split = kw.split(":")
            name = split[0].strip()
            value = split[1].strip()
        else:
            name = ""
            value = kw
        kw_dicts.append({
            "name": name,
            "value": value,
            "synonyms": ""
        })
    return kw_dicts
