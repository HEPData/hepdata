from hepdata.modules.records.utils.common import infer_file_type
import unittest


class SubmissionUtilsTest(unittest.TestCase):
    def test_url_pattern(self):
        test_urls = [
            {"url": "http://amcfast.hepforge.org/", "exp_result": "hepforge"},
            {"url": "https://bitbucket.org/eamonnmag/automacron-evaluation",
             "exp_result": "bitbucket"},
            {"url": "http://sourceforge.net/projects/isacommons/",
             "exp_result": "sourceforge"},
            {"url": "http://hepdata.net/record/11085", "exp_result": "zenodo"},
            {"url": "https://github.com/HEPData/hepdata",
             "exp_result": "github"}
        ]

        for url_group in test_urls:
            url_type = infer_file_type(url_group["url"])
            self.assertEqual(url_group["exp_result"], url_type)
        self.assertEqual(True, True)

    def test_file_extension_pattern(self):
        test_files = [
            {"file": "test.py", "exp_result": "Python"},
            {"file": "test.cpp", "exp_result": "C++"},
            {"file": "test.c", "exp_result": "C"},
            {"file": "test.sh", "exp_result": "Bash Shell"},
            {"file": "test.root", "exp_result": "ROOT"},
            {"file": "test.docx", "exp_result": "docx"},
            {"file": "test", "exp_result": "Unknown File Type"}
        ]

        for file_group in test_files:
            extension = infer_file_type(file_group["file"])
            self.assertEqual(file_group["exp_result"], extension)


if __name__ == '__main__':
    unittest.main()
