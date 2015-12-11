from invenio_db import db

__author__ = 'eamonnmaguire'


class DailyAccessStatistic(db.Model):
    __tablename__ = "daily_access_statistic"

    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)

    publication_recid = db.Column(db.Integer)
    day = db.Column(db.Date, nullable=False)

    count = db.Column(db.Integer)