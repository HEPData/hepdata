import tempfile
import zipfile
from shutil import rmtree

from shutil import move

from hepdata_converter_ws_client import convert

from hepdata.config import CFG_CONVERTER_URL
from hepdata.modules.records.utils.common import find_file_in_directory


def convert_zip_archive(input_archive, output_archive, options):
    """ Convert a zip archive into a targz path with given options. """
    input_root_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(input_archive, 'r') as zip_archive:
        zip_archive.extractall(path=input_root_dir)

    # Find the appropriate file/directory in the input archive
    input = options.get('input_format', 'yaml')
    validation = find_file_in_directory(
        input_root_dir,
        lambda x: x == 'submission.yaml' if input == 'yaml' else x.endswith('.oldhepdata')
    )
    if not validation:
        return None

    input_directory, input_file = validation

    successful = convert(
        CFG_CONVERTER_URL,
        input_directory if input == 'yaml' else input_file,
        output=output_archive,
        options=options,
        extract=False,
    )
    rmtree(input_root_dir)

    # Error occurred, the output is a HTML file
    if not successful:
        output_file = output_archive[:-7] + '.html'
    else:
        output_file = output_archive
    move(output_archive, output_file)

    return output_file


def convert_oldhepdata_to_yaml(input_path, output_path):
    """ Converts the data on the server from oldhepdata format to the new one. """
    options = {
        'input_format': 'oldhepdata',
        'output_format': 'yaml',
    }
    successful = convert(
        CFG_CONVERTER_URL,
        input_path,
        output=output_path,
        options=options
    )

    return successful
