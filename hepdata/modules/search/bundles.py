from invenio_assets import NpmBundle

__author__ = 'eamonnmaguire'

search_js = NpmBundle(
    'js/lib/typeahead.bundle.min.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.search.%(version)s.js"
)