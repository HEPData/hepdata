import os
import tarfile
import zipfile

from flask import current_app

from hepdata.modules.records.utils.common import remove_file_extension


def extract(file_name, file_path, time_stamp):
    unzipped_path = os.path.join(current_app.config['CFG_DATADIR'],
                                 str(id), time_stamp, remove_file_extension(file_name))

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
