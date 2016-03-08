__author__ = 'eamonnmaguire'

from invenio_assets import NpmBundle

vis_js = NpmBundle(
    'node_modules/d3/d3.min.js',
    'node_modules/d3-tip/index.js',
    'js/dataviewer.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.vis.%(version)s.js",
    npm={
        "d3": "~3.5.12",
        "d3-tip": "~0.6.7"
    }
)
