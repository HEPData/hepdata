from hepdata.modules.inspire_api.marcxml_parser import expand_date
from hepdata.modules.inspire_api.views import get_inspire_record_information


class MARCXMLParserTest():
    def test_date_expansion(self):
        print('___test_date_expansion___')
        dates = [
            {"test": "2012", "expected": "2012-01-01"},
            {"test": "", "expected": ""},
            {"test": "2011-08", "expected": "2011-08-01"},
            {"test": "2012-09", "expected": "2012-09-01"},
            {"test": "2002-09-01", "expected": "2002-09-01"}
        ]

        for date in dates:
            assert date["expected"] == expand_date(date["test"])

    def test_parser(self):
        test_data = [{"inspire_id": "1245023",
                      "title": "High-statistics study of $K^0_S$ pair "
                               "production in two-photon collisions",
                      "creation_date": "2013-07-29"},

                     {"inspire_id": "1183818",
                      "title": "Measurements of the pseudorapidity dependence "
                               "of the total transverse energy "
                               "in proton-proton "
                               "collisions at $\sqrt{s}=7$ TeV with ATLAS",
                      "creation_date": "2012-08-01"}
                     ]

        for test in test_data:
            content, status = get_inspire_record_information(
                test["inspire_id"])
            assert content["title"][0] == test["title"]
            assert content["creation_date"] == test["creation_date"]
