from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from invenio_db import db

from hepdata.modules.records.subscribers.api import get_users_subscribed_to_record, \
    get_records_subscribed_by_current_user
from hepdata.modules.records.utils.common import get_or_create
from .models import Subscribers

blueprint = Blueprint(
    'subscribers',
    __name__,
    url_prefix='/subscriptions'
)


@blueprint.route('/list/record/<int:recid>', methods=['GET'])
@login_required
def list_subscribers_to_record(recid):
    subscribers = get_users_subscribed_to_record(recid)
    return jsonify(subscribers)


@blueprint.route('/list/', methods=['GET'])
@login_required
def list_subscriptions_for_user():
    subscribers = get_records_subscribed_by_current_user()
    return jsonify(subscribers)


@blueprint.route('/subscribe/<int:recid>', methods=['POST'])
@login_required
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


@blueprint.route('/unsubscribe/<int:recid>', methods=['POST'])
@login_required
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
