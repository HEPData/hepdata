from operator import or_
from invenio_accounts.models import User
from hepdata.modules.records.models import SubmissionParticipant

__author__ = 'eamonnmaguire'

from flask.ext.login import current_user
from invenio_db import db


def setup_app(app):

    def user_is_admin_or_coordinator():
        if current_user.is_authorized:
            id = int(current_user.get_id())
            with db.session.no_autoflush:
                roles = User.query.filter(
                    id=id).filter(or_(User.roles.any(name='coordinator'),
                                      User.roles.any(name='admin'))).all()

            return len(roles) > 0
        return False

    @app.context_processor
    def is_coordinator_or_admin():
        """
            Determines if the user is an admin or coordinator given their
            assigned accRoles.
            :return: true if the user is a coordinator or administrator,
            false otherwise
        """
        return dict(user_is_coordinator_or_admin=user_is_admin_or_coordinator())

    @app.context_processor
    def show_dashboard():
        """
        Determines if a user should be able to see the submission overview page.
        :return:
        """
        if current_user.is_authorized:
            if user_is_admin_or_coordinator():
                return dict(show_dashboard=True)
            else:
                id = current_user.get_id()
                with db.session.no_autoflush:
                    submissions = SubmissionParticipant.query.filter(
                        SubmissionParticipant.user_account == id).count()

                return dict(show_dashboard=submissions > 0)

        return dict(show_dashboard=False)
