from invenio_assets import NpmBundle

__author__ = 'eamonnmaguire'

search_js = NpmBundle(
    'node_modules/d3/d3.min.js',
    'node_modules/d3-tip/index.js',
    'js/lib/typeahead.bundle.min.js',
    'js/search_utils.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.search.%(version)s.js"
)
