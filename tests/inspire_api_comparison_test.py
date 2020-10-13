# coding=utf

import pytest
import difflib

from hepdata.modules.new_inspire_api import views as new_views
from hepdata.modules.old_inspire_api import views as old_views


def string_diff(string1, string2):
    return [entry for entry in difflib.ndiff(string1, string2) if entry[0] != ' ']


# get inspire record information now and cache it to reduce run test run times
# note: the last record '1999999' does not exist, it is used to test that case
# record '143687' is a thesis
old_dict = {"1245023": old_views.get_inspire_record_information("1245023"),
            "1283842": old_views.get_inspire_record_information("1283842"),
            "1311487": old_views.get_inspire_record_information("1311487"),
            "1487726": old_views.get_inspire_record_information("1487726"),
            "143687": old_views.get_inspire_record_information("143687"),
            "1498199": old_views.get_inspire_record_information("1498199"),
            "1999999": old_views.get_inspire_record_information("1999999")}
new_dict = {"1245023": new_views.get_inspire_record_information("1245023"),
            "1283842": new_views.get_inspire_record_information("1283842"),
            "1311487": new_views.get_inspire_record_information("1311487"),
            "1487726": new_views.get_inspire_record_information("1487726"),
            "143687": new_views.get_inspire_record_information("143687"),
            "1498199": new_views.get_inspire_record_information("1498199"),
            "1999999": new_views.get_inspire_record_information("1999999")}


@pytest.mark.parametrize(
    "inspire_id",
    ["1245023", "1283842", "1311487", "1487726", "143687", "1498199", "1999999"]
)
def test_dict_keys(inspire_id):
    print('___test_dict_keys___')
    old_content, old_code = old_dict[inspire_id]
    new_content, new_code = new_dict[inspire_id]

    if inspire_id != "1999999":
        assert old_code == new_code
    assert old_content.keys() == new_content.keys()


@pytest.mark.parametrize(
    "inspire_id",
    ["1245023", "1283842", "1311487", "1487726", "143687", "1498199", "1999999"]
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

    if inspire_id != "1999999":
        assert old_code == new_code

    compare(inspire_id, old_content, new_content, dict_key)


def compare(inspire_id, old_content, new_content, dict_key, silent=False, max_string_diff=0.1):

    print("\rComparing {} of inspire {}.       ".format(dict_key, inspire_id), end='')

    # convert to normal string
    if str(type(old_content[dict_key])) == "<class 'bs4.element.NavigableString'>":
        old_content[dict_key] = str(old_content[dict_key])

    if dict_key == 'year':
        old_content[dict_key] = str(old_content[dict_key])
        new_content[dict_key] = str(new_content[dict_key])

    if silent is False:
        print(type(old_content[dict_key]))
        if type(old_content[dict_key]) in [str, list]:
            print(old_content[dict_key][:50])
            if len(old_content[dict_key]) > 50:
                print("...")
        else:
            print(old_content[dict_key])
        print(type(new_content[dict_key]))
        if type(new_content[dict_key]) in [str, list]:
            print(new_content[dict_key][:50])
            if len(new_content[dict_key]) > 50:
                print("...")
        else:
            print(new_content[dict_key])

    if dict_key == 'subject_area':

        # subject area strings changed, for example 'HEP Experiment' changed to 'hep-ex' or 'Experiment-HEP', allow it
        assert(old_content[dict_key] == new_content[dict_key] or old_content[dict_key] == [] or
               (any(['HEP Experiment' in entry for entry in old_content[dict_key]]) and any(['ex' in entry for entry in new_content[dict_key]])) or
               (any(['HEP Theory' in entry for entry in old_content[dict_key]]) and any(['th' in entry for entry in new_content[dict_key]])))

    elif dict_key == 'keywords':

        # keywords used to have 'name' & 'value', now it is just 'value' in the pattern: 'new_value' = 'old_name': 'old_value'
        old_keywords = set([entry['name'] + ": " + entry['value'] if entry['name'] != '' else entry['value'] for entry in old_content[dict_key]])
        new_keywords = set([":".join(entry['value'].split(':')[:2]) for entry in new_content[dict_key]])
        assert old_keywords - new_keywords == set()

    elif dict_key == 'type':

        # old 'type' list has more information than can be found in the new 'type', just check types
        assert isinstance(old_content[dict_key], list) and isinstance(new_content[dict_key], list)

    elif type(old_content[dict_key]) is str and type(new_content[dict_key]) is str:

        # allow 1 year difference in 'year' keyword entry (different versions of same record?)
        if (dict_key == 'year' and old_content[dict_key].isdigit() and new_content[dict_key].isdigit() and
           abs(int(old_content[dict_key]) - int(new_content[dict_key])) == 1):
            return

        # if old is contained in new then allow it
        if old_content[dict_key] in new_content[dict_key]:
            return

        # if all journal info is 'No Journal Information' then mark it as passed
        if dict_key == 'journal_info' and old_content['journal_info'] == 'No Journal Information':
            return

        # some strings have been updated (e.g. abstract or journal name), allow for up to 10% difference (default)
        stringdiff = string_diff(old_content[dict_key], new_content[dict_key])
        assert float(len(stringdiff)) / 2 / len(old_content[dict_key]) < max_string_diff  # at most 10% difference (default)
        if len(stringdiff) != 0 and silent is False:
            print("Warning: {} % difference in strings.".format(float(len(stringdiff)) / 2 / len(old_content[dict_key]) * 100))

    else:

        # last case scenario
        assert(
            # exact match
            old_content[dict_key] == new_content[dict_key] or
            # old is None or empty string
            old_content[dict_key] in [None, ''] or
            # new contains old
            (type(old_content[dict_key]) == list and type(new_content[dict_key]) == list and all([entry in new_content[dict_key] for entry in old_content[dict_key]]))
        )
