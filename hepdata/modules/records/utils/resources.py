import os

from flask import current_app

__author__ = 'eamonnmaguire'


def download_resource_file(recid, resource_path):
    """
    :param inspire_id:
    :return:
    """
    base_url = "http://hepdata.cedar.ac.uk/{}"

    output_location = os.path.join(current_app.config['CFG_DATADIR'], str(recid), 'resources')
    print output_location

    if not os.path.exists(output_location):
        os.makedirs(output_location)

    import urllib2

    url = resource_path
    if 'resource' in resource_path:
        url = base_url.format(resource_path)

    response = urllib2.urlopen(url)
    contents = response.read()
    # save to tmp file

    file_parts = resource_path.split('/')
    file_name = file_parts[-1]

    # this should only happen when a directory is referenced,
    # in which case it's a HTML file.
    if file_name == "":
        file_name = "index.html"

    with open(os.path.join(output_location, file_name), 'w') as resource_file:
        resource_file.write(contents)

    return os.path.join(output_location, file_name)
