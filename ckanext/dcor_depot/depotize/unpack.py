import pathlib
import shutil
import sys

from ..util import check_md5


def get_working_directory(path):
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError("File not found: {}".format(path))
    elif path.is_dir():
        raise ValueError("File must be a tar archive: {}".format(path))
    return path.with_name(path.name + "_depotize")


def unpack(path, verbose=0):
    """Check MD5 sum and unpack a tar file to `original/path_depotize/data/`

    Unpacking is skipped if the 'data' directory already exists.
    """
    path = pathlib.Path(path)
    wdir = get_working_directory(path)
    datadir = wdir / "data"
    if datadir.exists():
        if verbose > 0:
            print("Skipping extraction, because 'data' directory exists.")
    else:
        # check MD5 sum if applicable
        md5path = path.with_name(path.name + ".md5")
        if md5path.exists():
            wdir.mkdir(parents=True, exist_ok=True)
            md5sum = md5path.read_text().split()[0]
            check_md5(path, md5sum)
            shutil.copy2(md5path, wdir)
            if verbose > 0:
                print("MD5 sum OK")
        # extract archive
        datadir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.unpack_archive(path, extract_dir=datadir)
        except BaseException:
            shutil.rmtree(datadir, ignore_errors=True)
            raise
    return datadir


if __name__ == "__main__":
    unpack(sys.argv[-1])
