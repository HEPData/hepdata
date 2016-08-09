from flask import Blueprint, jsonify
from flask.ext.login import login_required, current_user
from invenio_db import db

from hepdata.modules.records.subscribers.api import get_users_subscribed_to_record, \
    get_records_subscribed_by_current_user
from hepdata.modules.records.utils.common import get_or_create
from .models import Subscribers

blueprint = Blueprint(
    'subcribers',
    __name__,
    url_prefix='/subscriptions'
)


@login_required
@blueprint.route('/subscribe/<int:recid>', methods=['POST'])
def subscribe(recid):
    record_subscribers = get_or_create(db.session, Subscribers, publication_recid=recid)

    try:
        if not current_user in record_subscribers.subscribers:
            record_subscribers.subscribers.append(current_user)

        db.session.add(record_subscribers)
        db.session.commit()
        return jsonify({"success": True})
    except:
        db.session.rollback()
        return jsonify({"success": False, "status_code": 500})


@login_required
@blueprint.route('/list/record/<int:recid>', methods=['GET'])
def list_subscribers_to_record(recid):
    subscribers = get_users_subscribed_to_record(recid)
    return jsonify(subscribers)


@login_required
@blueprint.route('/list/', methods=['GET'])
def list_subscriptions_for_user():
    subscribers = get_records_subscribed_by_current_user()
    return jsonify(subscribers)


@login_required
@blueprint.route('/unsubscribe/<int:recid>', methods=['POST'])
def unsubscribe(recid):
    record_subscribers = get_or_create(db.session, Subscribers,
                                       publication_recid=recid)

    try:
        if current_user in record_subscribers.subscribers:
            record_subscribers.subscribers.remove(current_user)

        db.session.add(record_subscribers)
        db.session.commit()
        return jsonify({"success": True})
    except:
        db.session.rollback()
        return jsonify({"success": False, "status_code": 500})
