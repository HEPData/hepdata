# -*- coding: utf-8 -*-
#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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

"""HEPData CLI module."""

from __future__ import absolute_import, print_function
import click
from flask.ext.cli import with_appcontext
from invenio_base.app import create_cli
from .factory import create_app
from hepdata.config import CFG_PUB_TYPE
from hepdata.ext.elasticsearch.api import reindex_all, \
    get_records_matching_field, record_exists
from hepdata.modules.records.utils.submission import unload_submission
from hepdata.modules.records.migrator.api import load_files, update_submissions

cli = create_cli(create_app=create_app)

default_recids = 'ins202932,ins1187688,ins67677,ins135836,ins1389108,ins1373299,ins1242869,ins1311487,ins1323075'


@cli.command()
@with_appcontext
@click.option('--inspireids', '-i', default=default_recids,
              help='A comma separated list of recids to load.')
@click.option('--recreate_index', '-rc', default=True, type=bool,
              help='Whether or not to recreate the index')
@click.option('--tweet', '-t', default=False, type=bool,
              help='Whether or not to send a tweet announcing the arrival of these records.')
def populate(inspireids, recreate_index, tweet):
    """Populate the DB with records.
        Usage: hepdata populate -i 'ins1262703' -rc False -t False
        :param inspireids:
        :param tweet:
        :param recreate_index:

    """
    from hepdata.ext.elasticsearch.api import recreate_index

    if recreate_index:
        recreate_index()

    files_to_load = parse_inspireids_from_string(inspireids)
    load_files(files_to_load, send_tweet=tweet)


@cli.command()
@with_appcontext
@click.option('--start', '-s', type=int, default=None,
              help='The start index from the total inspireids to load.')
@click.option('--end', '-e', default=None, type=int,
              help='The end index from the total inspireids to load.')
@click.option('--year', '-y', type=int, default=None,
              help='Filter all records modified since some point in time.')
@click.option('--missing-only', '-m', default=False,
              type=bool,
              help='This option will automatically find the inspire ids in the current '
                   'hepdata but not in this version and migrate them.')
def migrate(start, end, year=None, missing_only=False):
    """
    Migrates all content from HEPData
    :return:
    """
    if missing_only:
        inspire_ids = get_missing_records()
    else:
        inspire_ids = get_all_ids_in_current_system(year)

    print("Found {} inspire ids to load.".format(len(inspire_ids)))
    if start is not None:
        print("Slicing.")
        _slice = slice(int(start), end)
        inspire_ids = inspire_ids[_slice]
        print("Sliced, going to load {} records.".format(len(inspire_ids)))
        print(inspire_ids)

    load_files(inspire_ids)


@cli.command()
@with_appcontext
@click.option('--inspireids', '-i',
              help='A comma separated list of recids to load.')
@click.option('--update_record_info_only', '-ro', default=False, type=bool,
              help='True if you just want to update the publication information.')
def update(inspireids, update_record_info_only):
    """
    Given a list of record ids, can update the contents of the whole submission, or just the record information
    via the update_record_info_only option.
    Usage: hepdata update -i 'insXXX' -ro True|False
    :param inspireids: comma separated list of inspire ids, e.g. ins222121
    :param update_record_info_only: if True, will only up the record information, and won't update the data files.
    :return:
    """
    records_to_update = parse_inspireids_from_string(inspireids)
    update_submissions.delay(records_to_update, update_record_info_only)


@cli.command()
@with_appcontext
def find_duplicates_and_remove():
    """
    Will go through the application to find any duplicates then remove them.
    :return:
    """
    inspire_ids = get_all_ids_in_current_system(prepend_id_with="")

    duplicates = []
    for inspire_id in inspire_ids:
        matches = get_records_matching_field('inspire_id', inspire_id,
                                             doc_type=CFG_PUB_TYPE)
        if len(matches['hits']['hits']) > 1:
            duplicates.append(matches['hits']['hits'][0]['_source']['recid'])
    print('There are {} duplicates. Going to remove.'.format(len(duplicates)))
    do_unload(duplicates)


@cli.command()
@with_appcontext
def get_missing_records():
    inspire_ids = get_all_ids_in_current_system(prepend_id_with="")
    missing_ids = []
    for inspire_id in inspire_ids:
        if not record_exists(inspire_id):
            missing_ids.append(inspire_id)

    print("Missing {} records.".format(len(missing_ids)))
    print(missing_ids)
    return missing_ids


@cli.command()
@with_appcontext
@click.option('--recreate', '-rc', type=bool, default=False,
              help='Whether or not to recreate the index mappings as well. '
                   'This DELETES the entire index first.')
@click.option('--start', '-s', type=int, default=-1,
              help='Starting recid for the index operation.')
@click.option('--end', '-e', type=int, default=-1,
              help='End recid for the index operation.')
@click.option('--batch', '-b', type=int, default=50,
              help='Number of records to index at a time.')
def reindex(recreate, start, end, batch):
    reindex_all(recreate=recreate, start=start, end=end, batch=batch)


@cli.command()
@with_appcontext
@click.option('--inspireids', '-i', type=str,
              help='Load specific recids in to the system.')
@click.option('--tweet', '-t', default=False, type=bool,
              help='Whether or not to send a tweet announcing the arrival of these records.')
def load(inspireids, tweet):
    """
    Remove records given their HEPData IDs from the database.
    Removes all database entries, leaves the files on the server.
    :param inspireids: list of record IDs to load
    :return:
    """
    processed_record_ids = parse_inspireids_from_string(inspireids)

    load_files(processed_record_ids, send_tweet=tweet)


def parse_inspireids_from_string(records_to_unload):
    processed_record_ids = []
    records = records_to_unload.split(',')
    for record_id in records:
        processed_record_ids.append(record_id.strip())
    return processed_record_ids


@cli.command()
@with_appcontext
@click.option('--recids', '-r', type=str,
              help='Unload specific recids in to the system.')
def unload(recids):
    """
    Remove records given their HEPData IDs from the database.
    Removes all database entries, leaves the files on the server.
    :param record_ids: list of record IDs to remove
    :return:
    """
    records_to_unload = recids.split(',')

    processed_record_ids = []
    for record_id in records_to_unload:
        processed_record_ids.append(int(record_id.strip()))

    do_unload(processed_record_ids)


def do_unload(records_to_unload):
    for record_id in records_to_unload:
        unload_submission(record_id)


def get_all_ids_in_current_system(year=None, prepend_id_with="ins"):
    import requests, re

    brackets_re = re.compile(r'\[+|\]+')
    inspire_ids = []
    base_url = 'http://hepdata.cedar.ac.uk/allids/{0}'
    if year:
        base_url = base_url.format(year)
    else:
        base_url = base_url.format('')
    response = requests.get(base_url)
    if response.ok:
        _all_ids = response.text
        for match in re.finditer('\[[0-9]+,[0-9]+,[0-9]+\]', _all_ids):
            start = match.start()
            end = match.end()
            # process the block which is of the form [inspire_id,xxx,xxx]
            id_block = brackets_re.sub("", _all_ids[start:end])
            id = id_block.split(',')[0].strip()
            if id != '0': inspire_ids.append(
                prepend_id_with + "{}".format(id))
    return inspire_ids
