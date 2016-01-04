from flask import Blueprint, render_template
from flask.ext.login import login_required
__author__ = 'eamonnmaguire'


blueprint = Blueprint(
    'submission',
    __name__,
    url_prefix='/submit',
    template_folder='templates',
    static_folder='static'
)

@login_required
@blueprint.route('/', methods=['GET'])
def submit():
    return render_template('hepdata_submission/submit.html')