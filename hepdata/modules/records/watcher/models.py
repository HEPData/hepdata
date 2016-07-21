from invenio_accounts.models import User
from invenio_db import db


class WatchList(db.Model):
    """
    WatchList is the main model for storing the query to be made for
    a watched query and the user who is watching it.
    """
    __tablename__ = "watchlist"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    watch_field = db.Column(db.String)
    watch_value = db.Column(db.String)

    watcher = db.Column(db.Integer, db.ForeignKey(User.id))
