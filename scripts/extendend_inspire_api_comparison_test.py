# -*- coding: utf-8 -*-

import requests
import sys
import os

from hepdata.modules.new_inspire_api import views as new_views
from hepdata.modules.old_inspire_api import views as old_views

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../tests/")

from inspire_api_comparison_test import compare  # noqa

if sys.version_info[0] > 2:
    unicode = None


print("__extendend_inspire_api_comparison_test__")


page = 1

while page < 500:

    response = requests.get("http://inspirehep.net/api/literature?q=external_system_identifiers.schema:HEPData&page={}".format(page))

    if response.status_code != 200:
        break
    else:
        page += 1

    for i, hit in enumerate(response.json()['hits']['hits']):

        inspire_id = hit['id']

        print("\rTesting inspire id {}, entry number: {}.".format(inspire_id, (page - 2) * 10 + i + 1), end='\n')

        old_content, old_status = old_views.get_inspire_record_information(inspire_id)
        new_content, new_status = new_views.get_inspire_record_information(inspire_id)

        assert old_status == new_status

        for dict_key in old_content.keys():

            try:
                compare(inspire_id, old_content, new_content, dict_key, silent=True, max_string_diff=1)
            except AssertionError:
                WarningColourStart = '\033[93m'
                WarningColourEnd = '\033[0m'
                print(WarningColourStart + "Failed on {}, {} vs {}.".format(dict_key, old_content[dict_key], new_content[dict_key]) + WarningColourEnd)

print("\rEND OF EXTENDED INSPIRE API TEST.                            ")
