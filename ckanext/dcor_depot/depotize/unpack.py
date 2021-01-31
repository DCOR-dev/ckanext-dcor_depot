import pathlib
import shutil
import sys


def get_working_directory(path):
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError("File not found: {}".format(path))
    elif path.is_dir():
        raise ValueError("File must be a tar archive: {}".format(path))
    return path.with_name(path.name + "_depotize")


def unpack(path, verbose=0):
    """Unpack a tar file to `original/path_depotize/data/`

    Unpacking is skipped if the 'data' directory already exists.
    """
    path = pathlib.Path(path)
    datadir = get_working_directory(path) / "data"
    if datadir.exists():
        if verbose > 0:
            print("Skipping extraction, because 'data' directory exists.")
    else:
        datadir.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(path, extract_dir=datadir)
    return datadir


if __name__ == "__main__":
    unpack(sys.argv[-1])
