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

    if str(type(old_content[dict_key])) == "<class 'bs4.element.NavigableString'>":
        if sys.version_info[0] > 2:
            old_content[dict_key] = str(old_content[dict_key])
        else:
            old_content[dict_key] = unicode(old_content[dict_key])

    print(type(old_content[dict_key]))
    if type(old_content[dict_key]) in [str, unicode, list]:
        print(old_content[dict_key][:50])
        if len(old_content[dict_key]) > 50:
            print("...")
    else:
        print(old_content[dict_key])
    print(type(new_content[dict_key]))
    if type(new_content[dict_key]) in [str, unicode, list]:
        print(new_content[dict_key][:50])
        if len(new_content[dict_key]) > 50:
            print("...")
    else:
        print(new_content[dict_key])

    if dict_key == 'subject_area':
        assert ((old_content[dict_key] == ['HEP Experiment'] and new_content[dict_key] == ['hep-ex']) or old_content[dict_key] == new_content[dict_key])

    elif dict_key == 'keywords':
        old_keywords = set([entry['name'] + ": " + entry['value'] if entry['name'] != '' else entry['value'] for entry in old_content[dict_key]])
        new_keywords = set([":".join(entry.split(':')[:2]) for entry in new_content[dict_key]])
        assert old_keywords - new_keywords == set()

    elif dict_key == 'type':
        # old 'type' is a list and there doesn't seem to be an equivalent in the new metadata
        pass

    elif type(old_content[dict_key]) in [str, unicode] and type(new_content[dict_key]) in [str, unicode]:
        stringdiff = string_diff(old_content[dict_key], new_content[dict_key])
        assert float(len(stringdiff)) / len(old_content[dict_key]) < 0.1   # at most 10% difference
        if len(stringdiff) != 0:
            print("Warning: {} % difference in strings.".format(float(len(stringdiff)) / len(old_content[dict_key]) * 100))

    else:
        assert old_content[dict_key] == new_content[dict_key] or old_content[dict_key] is None
