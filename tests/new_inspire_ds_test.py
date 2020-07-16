# coding=utf-8

import json
import pytest

from flask import url_for
from hepdata.modules.new_inspire_api.views import get_inspire_record_information
from hepdata.modules.new_inspire_api.parser import expand_date
from hepdata.modules.records.utils.common import decode_string


def test_endpoint(client, identifiers):
    print('___test_endpoint___')

    for test_identifier in identifiers:
        content = client.get(url_for('inspire_datasource.get_record_from_inspire', **{'id': test_identifier['inspire_id']}))

        assert (content.data is not None)
        record_info = json.loads(content.data)
        assert (record_info is not None)

        assert (record_info['query']['arxiv_id'] == test_identifier['arxiv'])


@pytest.mark.parametrize(
    "test, expected",
    [("2012", "2012-01-01"),
     ("", ""),
     ("2011-08", "2011-08-01"),
     ("2012-09", "2012-09-01"),
     ("2002-09-01", "2002-09-01")]
)
def test_date_expansion(test, expected):
    print('___test_date_expansion___')
    assert expand_date(test) == expected


@pytest.mark.parametrize(
    "inspire_id, title, creation_date, year, subject_area",
    [("1245023", "High-statistics study of $K^0_S$ pair production in two-photon collisions", "2013-07-29", 2013, ['hep-ex']),
     ("1183818", "Measurements of the pseudorapidity dependence of the total transverse energy in proton-proton collisions at $\sqrt{s}=7$ TeV with ATLAS",
      "2012-08-01", 2012, ["hep-ex"]),
     ("1407276", "Elastic scattering of negative pions by protons at 2 BeV/c", "1963-01-01", 1963, None),
     ("44234", "DIFFERENTIAL ELASTIC PION-PROTON SCATTERING AT 600-MEV, 650-MEV and 750-MEV", "2006-04-11", 2006, None),
     ("1187688", "Mesure de la polarisation du proton de recul dans la diffusion élastique pi+- p entre 550 et 1025 MeV", "1970-01-01", 1970, None),
     ("67677", "INELASTIC ELECTRON - DEUTERON SCATTERING AT HIGH-ENERGIES", "1971-01-01", 1971, None)]
)
def test_parser(inspire_id, title, creation_date, year, subject_area):
    content, status = get_inspire_record_information(inspire_id)

    assert decode_string(content["title"]) == decode_string(title)
    assert content["creation_date"] == creation_date
    assert int(content["year"]) == year
    if subject_area is not None:
        assert content["subject_area"] == subject_area
