from invenio_db import db
from unittest.mock import call

from hepdata.modules.submission.models import HEPSubmission, DataSubmission

from fixes.cleanup_index import cleanup_index_all, cleanup_index_batch


def test_cleanup_index_all(app, load_default_data, identifiers, mocker):
    index = app.config.get('OPENSEARCH_INDEX')

    m = mocker.patch('fixes.cleanup_index.cleanup_index_batch')

    # Should be no calls made at first as there is only one version of all submissions
    cleanup_index_all(index=index, synchronous=True)
    m.assert_not_called()
    m.reset_mock()

    # Create a new version for ins1283842
    new_submission = HEPSubmission(publication_recid=1, inspire_id=identifiers[0]["inspire_id"], version=2, overall_status='finished')
    db.session.add(new_submission)
    db.session.commit()
    # New id should be 4
    assert(new_submission.id == 4)

    # Cleanup should now clean up id 1
    cleanup_index_all(index=index, synchronous=True)
    m.assert_called_once_with([1], index)
    m.reset_mock()

    # Create more new versions
    new_submission1 = HEPSubmission(publication_recid=1, inspire_id=identifiers[0]["inspire_id"], version=3, overall_status='finished')
    db.session.add(new_submission1)
    new_submission2 = HEPSubmission(publication_recid=1, inspire_id=identifiers[0]["inspire_id"], version=4, overall_status='todo')
    db.session.add(new_submission2)
    new_submission3 = HEPSubmission(publication_recid=16, inspire_id=identifiers[1]["inspire_id"], version=2, overall_status='finished')
    db.session.add(new_submission3)
    db.session.commit()
    assert(new_submission1.id == 5)
    assert(new_submission2.id == 6)
    assert(new_submission3.id == 7)

    # Cleanup should now clean up ids 1, 2 and 4 (ie versions lower than the highest finished version)
    cleanup_index_all(index=index, synchronous=True)
    m.assert_called_once_with([1, 2, 4], index)
    m.reset_mock()

    # Check batch size works
    cleanup_index_all(index=index, batch=2, synchronous=True)
    m.assert_has_calls([
        call([1, 2], index),
        call([4], index)
    ])
    m.reset_mock()

    cleanup_index_all(index=index, batch=1, synchronous=True)
    m.assert_has_calls([
        call([1], index),
        call([2], index),
        call([4], index)
    ])


def test_cleanup_index_batch(app, load_default_data, identifiers, mocker):
    index = app.config.get('OPENSEARCH_INDEX')

    def _create_new_versions(version, expected_range):
        # Create new HEPSubmission and DataSubmissions for ins1283842
        new_hep_submission = HEPSubmission(
            publication_recid=1, inspire_id=identifiers[0]["inspire_id"],
            version=version, overall_status='finished'
        )
        db.session.add(new_hep_submission)
        db.session.commit()
        new_data_submissions = []
        for i in range(5):
            new_data_submission = DataSubmission(
                publication_recid=1,
                associated_recid=1,
                version=version
            )
            db.session.add(new_data_submission)
            new_data_submissions.append(new_data_submission)
        db.session.commit()
        assert [x.id for x in new_data_submissions] == expected_range

    _create_new_versions(2, list(range(121, 126)))

    # Mock methods called so we can check they're called with correct parameters
    from invenio_search import RecordsSearch
    mock_records_search = mocker.patch.object(RecordsSearch, 'filter')

    # Reindex submission id 1 (pub_recid=1)
    # New version means the original data submissions (2-16) are
    # superceded so can be cleaned up
    cleanup_index_batch([1], index)
    assert mock_records_search.has_calls([
        call('terms', _id=list(range(2,16)))
    ])
    mock_records_search.reset_mock()

    # Create more new versions
    _create_new_versions(3, list(range(126, 131)))
    cleanup_index_batch([1], index)
    assert mock_records_search.has_calls([
        call('terms', _id=list(range(2,16)) + list(range(126, 131)))
    ])
    mock_records_search.reset_mock()

    # Clean up with id 17, for which there are no old versions
    # - should mean that filter is not called.
    cleanup_index_batch([17], index)
    mock_records_search.assert_not_called()
