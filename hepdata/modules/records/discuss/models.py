from invenio_db import db

datareview_messages = db.Table('discussion_messages',
                               db.Column('discussion_id', db.Integer,
                                         db.ForeignKey('discussion.id')),
                               db.Column('message_id', db.Integer,
                                         db.ForeignKey(
                                             'message.id')))


class Discussion(db.Model):
    """
    Discussion is the main model for storing the discussions
    relating to a particular record.
    """
    __tablename__ = "discussion"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # we store the publication recid and the version so that we know
    # exactly which version a discussion is relating to. Otherwise
    # there is the danger
    publication_recid = db.Column(db.Integer)
    version = db.Column(db.Integer, default=1)

    # e.g. Table 1 would be 1, or for all tables, we'd just use -1.
    # This means we can ask questions
    focus_table = db.Column(db.Integer, default=-1)

    messages = db.relationship("Message",
                               secondary="discussion_messages",
                               cascade="all,delete")
