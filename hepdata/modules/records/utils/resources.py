import os
from hepdata.config import CFG_DATADIR

__author__ = 'eamonnmaguire'


def download_resource_file(recid, resource_path):
    """
    :param inspire_id:
    :return:
    """
    base_url = "http://hepdata.cedar.ac.uk/{}"

    output_location = os.path.join(CFG_DATADIR, str(recid), 'resources')

    if not os.path.exists(output_location):
        os.makedirs(output_location)

    import urllib2

    response = urllib2.urlopen(base_url.format(resource_path))
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
