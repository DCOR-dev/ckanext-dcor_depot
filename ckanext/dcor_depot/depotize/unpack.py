import pathlib
import shutil
import sys


def unpack(path):
    """Unpack a tar file to `original/path_depotize/data/`"""
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError("File not found: {}".format(path))
    elif path.is_dir():
        raise ValueError("File must be a tar archive: {}".format(path))
    datadir = path.with_name(path.name + "_depotize") / "data"
    datadir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(path, extract_dir=datadir)
    return datadir


if __name__ == "__main__":
    unpack(sys.argv[-1])
