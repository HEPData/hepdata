from invenio_accounts.models import User

__author__ = 'eamonnmaguire'


def get_coordinators_in_system():
    """
    Utility function to get all coordinator users in the database.
    :return: list of coordinator ids, nicknames, and emails.
    """

    coordinators = User.query.filter(User.roles.any(name='coordinator')).all()

    to_return = [{'id': coordinator.id, 'nickname': coordinator.email,
                  'email': coordinator.email} for coordinator in coordinators]

    return to_return


def has_role(user, required_role):
    """
    Determines if a user has a particular role
    :param user: a current_user object
    :param required_role: e.g. 'admin'
    :return: True if the user has the role. False otherwise
    """
    for role in user.roles:
        if role.name == required_role:
            return True
    return False
