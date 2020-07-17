# coding=utf-8
import json

from flask import url_for

from hepdata.modules.old_inspire_api.marcxml_parser import expand_date
from hepdata.modules.old_inspire_api.views import get_inspire_record_information
from hepdata.modules.records.utils.common import decode_string


def test_endpoint(client, identifiers):
    print('___test_endpoint___')

    for test_identifier in identifiers:
        content = client.get(
            url_for('inspire_datasource.get_record_from_inspire',
                    **{'id': test_identifier['inspire_id']}),
            follow_redirects=True)
        assert (content.data is not None)
        record_info = json.loads(content.data)
        assert (record_info is not None)

        assert (record_info['query']['arxiv_id'] == test_identifier['arxiv'])


def test_date_expansion():
    print('___test_date_expansion___')
    dates = [
        {"test": "2012", "expected": "2012-01-01"},
        {"test": "", "expected": ""},
        {"test": "2011-08", "expected": "2011-08-01"},
        {"test": "2012-09", "expected": "2012-09-01"},
        {"test": "2002-09-01", "expected": "2002-09-01"}
    ]

    for date in dates:
        assert (date["expected"] == expand_date(date["test"]))


def test_parser():
    test_data = [{"inspire_id": "1245023",
                  "title": "High-statistics study of $K^0_S$ pair "
                           "production in two-photon collisions",
                  "creation_date": "2013-07-29", "year": 2013,
                  "subject_area": ['HEP Experiment']},

                 {"inspire_id": "1183818",
                  "title": "Measurements of the pseudorapidity dependence "
                           "of the total transverse energy "
                           "in proton-proton "
                           "collisions at $\\sqrt{s}=7$ TeV with ATLAS",
                  "creation_date": "2012-08-01",
                  "year": 2012,
                  "subject_area": ["HEP Experiment"]},
                 {"inspire_id": "1407276",
                  "title": "Elastic scattering of negative pions by protons at 2 BeV/c",
                  "creation_date": "1963-01-01",
                  "year": 1963},
                 {"inspire_id": "44234",
                  "title": "DIFFERENTIAL ELASTIC PION-PROTON SCATTERING AT 600-MEV, 650-MEV and 750-MEV",
                  "creation_date": "2006-04-11",
                  "year": 2006},
                 {"inspire_id": "1187688",
                  "title": "Mesure de la polarisation du proton de recul dans la diffusion élastique "
                           "pi+- p entre 550 et 1025 MeV",
                  "creation_date": "1970-01-01",
                  "year": 1970},
                 {"inspire_id": "67677",
                  "title": "INELASTIC ELECTRON - DEUTERON SCATTERING AT HIGH-ENERGIES",
                  "creation_date": "1971-01-01",
                  "year": 1971
                  }
                 ]

    for test in test_data:
        content, status = get_inspire_record_information(
            test["inspire_id"])

        assert (decode_string(content["title"]) == decode_string(test["title"]))
        assert (content["creation_date"] == test["creation_date"])
        assert (int(content["year"]) == test["year"])
        if 'subject_area' in test:
            assert (content["subject_area"] == test["subject_area"])
