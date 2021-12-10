# -*- coding: utf-8 -*-
#
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

"""YAML Processing Utils."""

import os

from hepdata.modules.records.utils.data_processing_utils import str_presenter
import shutil
import yaml
from yaml import CSafeLoader as Loader, CSafeDumper as Dumper
import zipfile
from datetime import datetime
from dateutil.parser import parse

import logging
logging.basicConfig()
log = logging.getLogger(__name__)

def write_submission_yaml_block(document, submission_yaml,
                                type="info"):
    submission_yaml.write("---\n")
    cleanup_yaml(document, type)
    Dumper.add_representer(str, str_presenter)
    yaml.dump(document, submission_yaml, allow_unicode=True, Dumper=Dumper)
    submission_yaml.write("\n")


def split_files(file_location, output_location):
    """
    :param file_location: input yaml file location
    :param output_location: output directory path
    """
    last_updated = datetime.utcnow()
    try:
        file_documents = yaml.load_all(open(file_location, 'r'), Loader=Loader)

        # make a submission directory where all the files will be stored.
        # delete a directory in the event that it exists.
        if os.path.exists(output_location):
            shutil.rmtree(output_location)

        os.makedirs(output_location)

        with open(os.path.join(output_location, "submission.yaml"),
                  'w') as submission_yaml:
            for document in file_documents:
                if not document:
                    continue
                elif "name" not in document:
                    if "dateupdated" in document:
                        try:
                            last_updated = parse(document['dateupdated'], dayfirst=True)
                        except ValueError as ve:
                            last_updated = datetime.utcnow()
                    else:
                        last_updated = datetime.utcnow()
                    write_submission_yaml_block(
                        document, submission_yaml)
                else:
                    file_name = document.get("name", '').replace(' ', '_').replace('/', '-') + ".yaml"
                    document["data_file"] = file_name

                    with open(os.path.join(output_location, file_name),
                              'w') as data_file:
                        Dumper.add_representer(str, str_presenter)
                        yaml.dump({
                            "independent_variables":
                                cleanup_data_yaml(
                                    document.get("independent_variables")),
                            "dependent_variables":
                                cleanup_data_yaml(
                                    document.get("dependent_variables"))
                            },
                            data_file, allow_unicode=True, Dumper=Dumper)

                    write_submission_yaml_block(document,
                                                submission_yaml,
                                                type="record")

    except (yaml.scanner.ScannerError, yaml.parser.ParserError) as ye:
        return ye, last_updated
    except Exception as e:
        log.exception('Error extracting YAML from %s, %s', file_location, e)
        message = f"Unable to extract YAML from file {os.path.basename(file_location)}. " \
            + "Please check the file is valid YAML and try again later. Contact info@hepdata.net if problems persist."
        raise ValueError(message) from e
    return None, last_updated


def cleanup_data_yaml(yaml):
    """
    Casts strings to numbers where possible.

    :param yaml:
    :return:
    """
    if yaml is None:
        yaml = []

    convert_string_to_numbers(yaml)

    return yaml


def convert_string_to_numbers(variable_set):
    fields = ["value", "high", "low"]

    if variable_set is not None:
        for variable in variable_set:
            if type(variable) is dict:
                if variable["values"] is not None:
                    for value_item in variable["values"]:
                        try:
                            for field in fields:
                                if field in value_item:
                                    value_item[field] = float(
                                        value_item[field])
                        except ValueError:
                            pass
                else:
                    variable["values"] = []
    else:
        variable_set = []


def cleanup_yaml(yaml, type):
    keys_to_remove = ["independent_variables",
                      "dependent_variables", "publicationyear", "preprintyear"]
    remove_keys(yaml, keys_to_remove)

    if type is 'info':
        add_field_if_needed(yaml, 'comment',
                            'No description provided.')
    else:
        add_field_if_needed(yaml, 'keywords', [])
        add_field_if_needed(yaml, 'description',
                            'No description provided.')

    if "label" in yaml:
        yaml["location"] = yaml["label"]
        del yaml["label"]


def add_field_if_needed(yaml, field_name, default_value):
    if not (field_name in yaml):
        yaml[field_name] = default_value


def remove_keys(yaml, to_remove):
    """
    :param yaml:
    :return:
    """
    for key in yaml:
        if not yaml[key]:
            to_remove.append(key)

    for key in to_remove:
        if key in yaml:
            del yaml[key]
