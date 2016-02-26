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
from ordereddict import OrderedDict

__author__ = 'eamonnmaguire'


def process_independent_variables(table_contents, x_axes,
                                  independent_variable_headers):
    if table_contents["independent_variables"]:
        count = 0
        for x_axis in table_contents["independent_variables"]:

            if x_axis["values"]:
                units = x_axis['header']['units'] if 'units' in x_axis[
                    'header'] else ''
                x_header = x_axis['header']['name']
                if units is not '':
                    x_header += ' [' + units + "]"

                if x_header in x_axes:
                    # sometimes, the x headers can be the same.
                    # We must account for this. 
                    x_header += '__{0}'.format(count)

                x_axes[x_header] = []

                # if x_header not in x_headers:
                independent_variable_headers.append(
                    {"name": x_header, "colspan": 1})
                for value in x_axis["values"]:
                    x_axes[x_header].append(value)

            count += 1


def process_dependent_variables(group_count, record, table_contents,
                                tmp_values, independent_variables,
                                dependent_variable_headers):
    for y_axis in table_contents["dependent_variables"]:

        qualifiers = {}
        if "qualifiers" in y_axis:
            for qualifier in y_axis["qualifiers"]:
                # colspan = len(y_axis["qualifiers"][qualifier])
                qualifier_name = qualifier["name"]

                if qualifier_name not in qualifiers:
                    qualifiers[qualifier_name] = 0
                else:
                    qualifiers[qualifier_name] += 1
                    count = qualifiers[qualifier_name]
                    qualifier_name = "{0}-{1}".format(qualifier_name, count)

                if qualifier_name not in record["qualifiers"].keys():
                    record["qualifier_order"].append(qualifier_name)
                    record["qualifiers"][qualifier_name] = []

                record["qualifiers"][qualifier_name].append(
                    {"type": qualifier["name"],
                     "value": str(qualifier["value"]) + (
                         ' ' + qualifier['units'] if 'units' in qualifier else ''),
                     "colspan": 1, "group": group_count})

            # attempt column merge
            for qualifier in record["qualifiers"]:
                values = record["qualifiers"][qualifier]
                merged_values = []
                last_value = None
                for counter, value in enumerate(values):
                    if not last_value:
                        last_value = value
                    else:
                        if last_value["type"] == value["type"] \
                            and last_value["value"] == value["value"]:

                            last_value["colspan"] += 1
                        else:
                            merged_values.append(last_value)
                            last_value = value

                    if counter == len(values) - 1:
                        merged_values.append(last_value)

                record["qualifiers"][qualifier] = merged_values

        units = y_axis['header']['units'] if 'units' in y_axis[
            'header'] else ''
        y_header = y_axis['header']['name']
        if units is not '':
            y_header += ' [' + units + ']'
        dependent_variable_headers.append({"name": y_header, "colspan": 1})

        count = 0
        for value in y_axis["values"]:

            if count not in tmp_values.keys():
                x = []
                for x_header in independent_variables:
                    x.append(independent_variables[x_header][count])
                tmp_values[count] = {"x": x, "y": []}

            y_record = value
            y_record["group"] = group_count

            if "errors" not in y_record:
                y_record["errors"] = [{"symerror": 0, "hide": True}]
            else:
                # process the labels to ensure uniqueness
                observed_error_labels = {}
                for error in y_record["errors"]:
                    error_label = error.get("label")

                    if error_label not in observed_error_labels:
                        observed_error_labels[error_label] = 0
                    observed_error_labels[error_label] += 1

                    if observed_error_labels[error_label] > 1:
                        error["label"] = error_label + "_" + str(
                            observed_error_labels[error_label])

                    # append "_1" to first error label that has a duplicate
                    if observed_error_labels[error_label] == 2:
                        for error1 in y_record["errors"]:
                            error1_label = error1.get("label")
                            if error1_label == error_label:
                                error1["label"] = error1_label + "_1"
                                break

            tmp_values[count]["y"].append(y_record)
            count += 1

        group_count += 1


def generate_table_structure(table_contents):
    """
    Creates a renderable structure from the table structure we've defined.
    :param table_contents:
    :return: a dictionary encompassing the qualifiers, headers and values
    """

    record = {"name": table_contents["name"], "doi": table_contents["doi"],
              "description": table_contents["title"], "qualifiers": {},
              "qualifier_order": [], "headers": [],
              "review": table_contents["review"],
              "associated_files": table_contents["associated_files"],
              "keywords": {},
              "values": []}

    # add in keywords
    for keyword in table_contents['keywords']:
        if keyword.name not in record['keywords']:
            record['keywords'][keyword.name] = []

        if keyword.value not in record['keywords'][keyword.name]:
            record['keywords'][keyword.name].append(keyword.value)

    tmp_values = {}
    x_axes = OrderedDict()
    x_headers = []
    process_independent_variables(table_contents, x_axes, x_headers)
    record["x_count"] = len(x_headers)
    record["headers"] += x_headers

    group_count = 0
    yheaders = []

    print x_axes

    process_dependent_variables(group_count, record, table_contents,
                                tmp_values, x_axes, yheaders)

    # attempt column merge
    last_yheader = None
    for counter, yheader in enumerate(yheaders):
        if not last_yheader:
            last_yheader = yheader
        else:
            if last_yheader["name"] == yheader["name"]:
                last_yheader["colspan"] += 1
            else:
                record["headers"].append(last_yheader)
                last_yheader = yheader
        if counter == len(yheaders) - 1:
            record["headers"].append(last_yheader)

    for tmp_value in tmp_values:
        record["values"].append(tmp_values[tmp_value])

    return record


def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
