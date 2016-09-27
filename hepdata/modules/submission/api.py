from hepdata.modules.submission.models import DataResource
from hepdata.modules.permissions.models import SubmissionParticipant
from hepdata.modules.submission.models import HEPSubmission

"""Common utilites used across the code base"""


def is_resource_added_to_submission(recid, version, resource_url):
    """
    Returns if a submission already has the given resource url
    :param recid:
    :param version:
    :param resource_url:
    :return:
    """
    return HEPSubmission.query.filter(HEPSubmission.publication_recid == recid,
                                      HEPSubmission.version == version,
                                      HEPSubmission.resources.any(
                                          DataResource.file_location == resource_url)).count() > 0


def get_latest_hepsubmission(*args, **kwargs):
    """
    Gets of creates a new HEPSubmission record
    :param recid: the publication record id
    :param coordinator: the user id of the user who owns this record
    :param status: e.g. todo, finished.
    :return: the newly created HEPSubmission object
    """

    hepsubmissions = HEPSubmission.query.filter_by(**kwargs).all()

    last = None
    for hepsubmission in hepsubmissions:
        if last is None:
            last = hepsubmission
        else:
            if hepsubmission.version > last.version:
                last = hepsubmission

    return last


def get_submission_participants_for_record(publication_recid):
    submission_participants = SubmissionParticipant.query.filter_by(
        publication_recid=publication_recid, status="primary").all()

    return submission_participants
