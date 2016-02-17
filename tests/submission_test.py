from hepdata.modules.records.utils.common import infer_file_type, contains_accepted_url, allowed_file
from hepdata.modules.submission.views import process_submission_payload


def test_submission_endpoint(app, client):
    submission = process_submission_payload(title="Test Submission", submitter_id=1,
                                            reviewer={'name': 'Eamonn', 'email': 'eamonnmag@gmail.com'},
                                            uploader={'name': 'Eamonn', 'email': 'eamonnmag@gmail.com'},
                                            send_upload_email=False)

    assert (submission is not None)


def test_allowed_file():
    assert (allowed_file('test.zip'))
    assert (allowed_file('test.tar'))
    assert (allowed_file('test.tar.gz'))
    assert (not allowed_file('test.pdf'))


def test_url_pattern():
    test_urls = [
        {"url": "http://amcfast.hepforge.org/", "exp_result": "hepforge"},
        {"url": "https://bitbucket.org/eamonnmag/automacron-evaluation",
         "exp_result": "bitbucket"},
        {"url": "http://sourceforge.net/projects/isacommons/",
         "exp_result": "sourceforge"},
        {"url": "http://zenodo.net/record/11085", "exp_result": "zenodo"},
        {"url": "https://github.com/HEPData/hepdata",
         "exp_result": "github"}
    ]

    for url_group in test_urls:
        contained, url_type = contains_accepted_url(url_group["url"])
        assert (url_group["exp_result"] == url_type)


def test_file_extension_pattern():
    test_files = [
        {"file": "test.py", "exp_result": "Python"},
        {"file": "test.cpp", "exp_result": "C++"},
        {"file": "test.c", "exp_result": "C"},
        {"file": "test.sh", "exp_result": "Bash Shell"},
        {"file": "test.root", "exp_result": "ROOT"},
        {"file": "test.docx", "exp_result": "docx"},
        {"file": "test", "exp_result": "resource"}
    ]

    for file_group in test_files:
        extension = infer_file_type(file_group["file"])
        assert (file_group["exp_result"] == extension)
