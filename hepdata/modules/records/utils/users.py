from invenio_accounts.models import User

__author__ = 'eamonnmaguire'


def get_coordinators_in_system():
    """
    Utility function to get all coordinator users in the database.
    :return: list of coordinator ids, nicknames, and emails.
    """
    from invenio_access.models import UserAccROLE
    from invenio_db import db

    coordinators = db.session.query(UserAccROLE, User)\
        .filter(UserAccROLE.id_accROLE == 1)\
        .filter(UserAccROLE.id_user == User.id)\
        .values(User.id, User.email, User.nickname)

    to_return = [{'id': coordinator.id, 'nickname': coordinator.nickname,
                  'email': coordinator.email} for coordinator in coordinators]

    return to_return
