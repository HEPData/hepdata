# coding=utf-8

import pytest
import difflib
import sys

from hepdata.modules.new_inspire_api import views as new_views
from hepdata.modules.inspire_api import views as old_views

if sys.version_info[0] > 2:
    unicode = None

def string_diff(string1, string2):
    return [entry for entry in difflib.ndiff(string1, string2) if entry[0] != ' ']


old_dict = {"1245023": old_views.get_inspire_record_information("1245023"),
            "1283842": old_views.get_inspire_record_information("1283842"),
            "1311487": old_views.get_inspire_record_information("1311487"),
            "1487726": old_views.get_inspire_record_information("1487726")}
new_dict = {"1245023": new_views.get_inspire_record_information("1245023"),
            "1283842": new_views.get_inspire_record_information("1283842"),
            "1311487": new_views.get_inspire_record_information("1311487"),
            "1487726": new_views.get_inspire_record_information("1487726")}


@pytest.mark.parametrize(
    "inspire_id",
    ["1245023", "1283842", "1311487", "1487726"]
)
def test_dict_keys(inspire_id):
    print('___test_dict_keys___')
    old_content, old_code = old_dict[inspire_id]
    new_content, new_code = new_dict[inspire_id]

    assert old_code == new_code
    assert old_content.keys() == new_content.keys()


@pytest.mark.parametrize(
    "inspire_id",
    ["1245023", "1283842", "1311487", "1487726"]
)
@pytest.mark.parametrize(
    "dict_key",
    ['journal_info', 'abstract', 'authors', 'creation_date', 'subject_area', 'year',
     'keywords', 'doi', 'title', 'collaborations', 'arxiv_id', 'type']
)
def test_dict_values(inspire_id, dict_key):
    print('___test_dict_keys___')

    old_content, old_code = old_dict[inspire_id]
    new_content, new_code = new_dict[inspire_id]

    assert old_code == new_code

    if type(old_content[dict_key]) in [str, unicode] and type(new_content[dict_key]) in [str, unicode]:
        stringdiff = string_diff(old_content[dict_key], new_content[dict_key])
        assert len(stringdiff) <= 2
        if len(stringdiff) != 0:
            print("Warning: ", old_content[dict_key], new_content[dict_key], stringdiff)
    else:
        assert old_content[dict_key] == new_content[dict_key] or old_content[dict_key] is None
