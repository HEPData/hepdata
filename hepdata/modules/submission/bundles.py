from invenio_assets import NpmBundle

__author__ = 'eamonnmaguire'


submission_js = NpmBundle(
    'js/inspire.js',
    filters='uglifyjs,jsmin',
    output="gen/hepdata-inspire.%(version)s.js",
)
