import tarfile
import zipfile

from hepdata.modules.records.utils.common import find_file_in_directory


def extract(file_name, file_path, unzipped_path):

    if file_name.endswith("tar.gz"):
        tar = tarfile.open(file_path, "r:gz")
        tar.extractall(path=unzipped_path)
        tar.close()
    elif file_name.endswith("tar"):
        tar = tarfile.open(file_path, "r:")
        tar.extractall(path=unzipped_path)
        tar.close()
    elif 'zip' in file_name:
        zipped_submission = zipfile.ZipFile(file_path)
        zipped_submission.printdir()

        zipped_submission.extractall(path=unzipped_path)

    return unzipped_path


def get_file_in_directory(path, extension):
    directory, file = find_file_in_directory(path, lambda x: x.endswith(extension))

    return file
