# This file is part of HEPData.
# Copyright (C) 2021 CERN.
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
from hepdata.modules.records.utils.common import truncate_string


def get_json_ld(ctx, submission_status, data_submission=None):
    """Generates JSON-LD metadata as a python dict

    :param type ctx: Context as would be passed to templates for a publication, data record or data resource
    :param type submission_status: Current status of the record's submission
    :return: dict containing metadata ready to be converted to JSON.
    :rtype: dict

    """
    if not ctx.get('record') or not ctx['record'].get('hepdata_doi') \
            or submission_status != 'finished':
        return {
            'error': 'JSON-LD is unavailable for this record; JSON-LD is only available for finalised records with DOIs.'
        }

    data = {
        "@context": "http://schema.org",
        "inLanguage": "en",
        "provider": {
            "@type": "Organization",
            "name": "HEPData"
        },
        "publisher": {
            "@type": "Organization",
            "name": "HEPData"
        },
        "version": ctx['version'],
        "identifier": [
            {
              "@type": "PropertyValue",
              "propertyID": "HEPDataRecord",
              "value": f"{ctx['site_url']}/record/ins{ctx['record']['inspire_id']}?version={ctx['version']}"
            },
            {
              "@type": "PropertyValue",
              "propertyID": "HEPDataRecordAlt",
              "value": f"{ctx['site_url']}/record/{ctx['record']['recid']}"
            }
        ],
        'datePublished': str(ctx['record']['last_updated'].year)
    }

    if ctx['record'].get('inspire_id') or ctx['record'].get('journal_info') != "No Journal Information":
        _add_is_based_on(data, ctx)

    _add_authors(data, ctx)

    if ctx['record_type'] == 'publication':
        _add_publication_info(data, ctx)
    elif ctx['record_type'] == 'table':
        _add_table_info(data, ctx, data_submission)
    elif ctx['record_type'] == 'resource':
        _add_resource_info(data, ctx)

    return data


def _add_is_based_on(data, ctx):
    is_based_on = []

    if ctx['record'].get('inspire_id'):
        is_based_on.append(
            {
                "@type": "ScholarlyArticle",
                "identifier": {
                     "@type": "PropertyValue",
                     "propertyID": "URL",
                     "value": f"https://inspirehep.net/literature/{ctx['record']['inspire_id']}"
                }
            }
        )

    if ctx['record'].get('doi'):
        is_based_on.append({
           "@id": f"https://doi.org/{ctx['record']['doi']}",
           "@type": "JournalArticle"
        })

    data["@reverse"] = {"isBasedOn": is_based_on}


def _add_authors(data, ctx):
    if ctx['record'].get('collaborations'):
        collaborations = [
            {
                "@type": "Organization",
                "name": f'{c} Collaboration'
            }
            for c in ctx['record'].get('collaborations')
        ]
        if len(collaborations) == 1:
            collaborations = collaborations[0]

        data['author'] = collaborations
        data['creator'] = collaborations
    else:
        authors = []
        for author in ctx['record'].get('summary_authors', []):
            author_data = {
                "@type": "Person",
                "name": author['full_name'],
            }
            if author.get('affiliation'):
                author_data['affiliation'] = {
                    "@type": "Organization",
                    "name": author['affiliation']
                }
            authors.append(author_data)

        data['author'] = authors
        data['creator'] = authors


def _add_publication_info(data, ctx):
    data["@type"] = "Dataset"
    data["additionalType"] = "Collection"
    data["@id"] = f"https://doi.org/{ctx['record']['hepdata_doi']}"
    data["url"] = f"{ctx['site_url']}/record/ins{ctx['record']['inspire_id']}?version={ctx['version']}"
    abstract = ctx['record'].get('data_abstract') or ctx['record'].get('abstract') or "No description available"
    data["description"] = truncate_string(abstract, max_chars=5000)
    data["name"] = truncate_string(ctx['record']['title'], max_chars=5000)

    has_part = []

    for table in ctx['data_tables']:
        description = table['description'] or "No description available"
        has_part.append({
            "@id": f"https://doi.org/{table['doi']}",
            "@type": "Dataset",
            "description": truncate_string(description, max_chars=5000),
            "name": table['name']
        })

    data['hasPart'] = has_part


def _add_table_info(data, ctx, data_submission):
    data["@type"] = "Dataset"
    data["additionalType"] = "Dataset"
    table_id = ctx['table_id_to_show']
    table_metadata = None
    for table in ctx['data_tables']:
        if table_id == table['id']:
            table_metadata = table
            break

    if table_metadata:
        data["@id"] = f"https://doi.org/{table_metadata['doi']}"
        data["name"] = table_metadata['name']
        if table_metadata['description']:
            data["description"] = truncate_string(table_metadata['description'], max_chars=5000)

    if data_submission:
        data["keywords"] = ', '.join([k.value for k in data_submission.keywords])
        data["url"] = f"{ctx['site_url']}/record/{data_submission.associated_recid}"

    data_downloads = []
    download_types = {
        'root': 'https://root.cern',
        'yaml': 'https://yaml.org',
        'csv': 'text/csv',
        'yoda': 'https://yoda.hepforge.org'
    }
    for download_type, format in download_types.items():
        data_downloads.append({
          "@type": "DataDownload",
          "contentUrl": f"{ctx['site_url']}/download/table/{ctx['table_id_to_show']}/{download_type}",
          "description": download_type.upper() + " file",
          "encodingFormat": format
        })

    data['distribution'] = data_downloads

    _add_is_part_of(data, ctx)
    data["includedInDataCatalog"] = {
        "@id": data["isPartOf"]["@id"],
        "@type": "DataCatalog",
        "url": data["isPartOf"]["url"]
    }


def _add_resource_info(data, ctx):
    data["@id"] = f"https://doi.org/{ctx['resource'].doi}"
    data["@type"] = "CreativeWork"
    data["additionalType"] = f"{ctx['resource'].file_type} file"
    data["contentUrl"] = f"{ctx['site_url']}/record/resource/{ctx['resource'].id}?view=true"
    description = ctx['resource'].file_description or "No file description available"
    data["description"] = truncate_string(description, max_chars=5000)
    name = f'"{ctx["resource_filename"]}" of "{ctx["record"]["title"]}"'
    data["name"] = truncate_string(name, max_chars=5000)
    data["url"] = f"{ctx['site_url']}/record/resource/{ctx['resource'].id}?landing_page=true"
    _add_is_part_of(data, ctx)


def _add_is_part_of(data, ctx):
    abstract = ctx['record'].get('data_abstract') or ctx['record'].get('abstract') or "No description available"
    data["isPartOf"] = {
        "@id": f"https://doi.org/{ctx['record'].get('hepdata_doi')}",
        "@type": "Dataset",
        "name": truncate_string(ctx['record']['title'], max_chars=5000),
        "description": truncate_string(abstract, max_chars=5000),
        "url": f"{ctx['site_url']}/record/ins{ctx['record']['inspire_id']}?version={ctx['version']}"
    }
