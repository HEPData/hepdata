__author__ = 'eamonnmaguire'

from invenio_assets import NpmBundle

vis_js = NpmBundle(
    'node_modules/d3/d3.min.js',
    'node_modules/d3-tip/index.js',
    'js/hepdata_common.js',
    'js/hepdata_loaders.js',
    'js/hepdata_reviews.js',
    'js/hepdata_tables.js',
    'js/hepdata_vis_common.js',
    'js/hepdata_vis_heatmap.js',
    'js/hepdata_vis_histogram.js',
    'js/hepdata_vis_pie.js',
    filters='jsmin,uglifyjs',
    output="gen/hepdata.vis.%(version)s.js",
    npm={
        "d3": "~3.5.12",
        "d3-tip": "~0.6.7"
    }
)
