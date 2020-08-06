# -*- coding: utf-8 -*-

import sys
import os
import math

from hepdata.resilient_requests import resilient_requests
from hepdata.modules.new_inspire_api import views as new_views
from hepdata.modules.old_inspire_api import views as old_views

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../tests/")

from inspire_api_comparison_test import compare  # noqa


print("__extended_inspire_api_comparison_test__")

page = 1
response = resilient_requests("get", "https://inspirehep.net/api/literature?q=external_system_identifiers.schema:HEPData&page={}".format(page))
total = int(response.json()['hits']['total'])


while page <= math.ceil(total / 10):

    response = resilient_requests("get", "https://inspirehep.net/api/literature?q=external_system_identifiers.schema:HEPData&page={}".format(page))
    response.raise_for_status()

    page += 1

    for i, hit in enumerate(response.json()['hits']['hits']):

        inspire_id = hit['id']

        print("\rTesting inspire id {}, entry number: {} of {}.".format(inspire_id, (page - 2) * 10 + i + 1, total), end='\n')

        try:
            old_content, old_status = old_views.get_inspire_record_information(inspire_id)
        except AttributeError:
            print("AttributeError in old inspire api")
            continue
        new_content, new_status = new_views.get_inspire_record_information(inspire_id)

        assert old_status == new_status

        for dict_key in old_content.keys():

            try:
                compare(inspire_id, old_content, new_content, dict_key, silent=True, max_string_diff=0.5)
            except AssertionError:
                WarningColourStart = '\033[93m'
                WarningColourEnd = '\033[0m'
                print(WarningColourStart + "Failed on {}, {} vs {}.".format(dict_key, old_content[dict_key], new_content[dict_key]) + WarningColourEnd)

else:
    print("\rEND OF EXTENDED INSPIRE API TEST.                            ")
