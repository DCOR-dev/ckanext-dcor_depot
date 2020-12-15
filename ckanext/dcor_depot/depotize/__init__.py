import pathlib
import shutil

from .check import check
from .convert import convert
from .scan import scan
from .unpack import unpack


def depotize(path, cleanup=True, abort_on_unknown=True, verbose=1):
    """Transform arbitrary .rtdc data to the depot structure

    The following tasks are performed:

    - unpack the tar file to `original/path/filename.tar_depotize/data`
    - scan the unpacked directory for RT-DC data (.rtdc and .tdms);
      found datasets are written to the text file
      `original/path/filename.tar_depotize/measurements.txt`
    - check whether the data files in `measurements.txt` are valid
      and store them in `check_usable.txt`
    - convert the data to compressed .rtdc files and create condensed
      datasets

    By default, the depot data are stored in the direcotry root in
    `/data/depots/internal/` and follow the directory structure
    `201X/2019-08/20/2019-08-20_1126_c083de*` where the allowed file names
    in this case are

    - 2019-08-20_1126_c083de.sha256sums a file containing SHA256 sums
    - 2019-08-20_1126_c083de_v1.rtdc the actual measurement
    - 2019-08-20_1126_c083de_v1_condensed.rtdc the condensed dataset
    - 2019-08-20_1126_c083de_ad1_m001_bg.png an ancillary image
    - 2019-08-20_1126_c083de_ad2_m002_bg.png another ancillary image
    """
    path = pathlib.Path(path).resolve()
    if path.is_dir():
        # iterate
        for ftar in path.rglob("*"):
            if ftar.suffix in [".tar", ".tar.gz"]:
                if not ftar.is_dir():
                    if depotize(ftar, cleanup=cleanup):
                        continue
                    else:
                        # User aborted
                        break
        return
    if verbose >= 1:
        print("Processing {}".format(path))
    # unpack and check mdf5 (if available)
    datadir = unpack(path)
    # scan unpacked directory
    scan_info, scan_lists = scan(datadir, verbose=verbose-1)
    if verbose >= 1:
        for key in ["datasets", "datasets excluded", "files unknown"]:
            if scan_info[key]:
                print(" {} {} (scan)".format(scan_info[key], key))

    if scan_info["files unknown"] and abort_on_unknown:
        print(" There were unknown files:")
        [print("  {}".format(ff)) for ff in scan_lists["files unknown"]]
        print("ABORTING!")
        return False

    check_res = check(datadir.parent / "measurements.txt", verbose=verbose-1)
    if verbose >= 1:
        for key in ["usable", "invalid", "violations", "alerts"]:
            if check_res[key]:
                print(" {} {} (check)".format(len(check_res[key]), key))

    convert(datadir.parent / "check_usable.txt", verbose=verbose-1)

    if cleanup:
        # remove data dir
        shutil.rmtree(datadir)
        # move tar file to archived_meta directory and remove data directory
        tdata = pathlib.Path("/data/archive/processed/") / path.name[:4]
        tdata.mkdir(exist_ok=True, parents=True)
        path.rename(tdata / path.name)
        tarn = shutil.make_archive(tdata / (path.name + "_meta"),
                                   format="tar",
                                   root_dir=datadir.parent,
                                   base_dir=datadir.parent)
        # move text files to metadata directory
        tmeta = pathlib.Path("/data/archive/archived_meta/") / path.name[:4]
        tmeta.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(tarn, tmeta / pathlib.Path(tarn).name)
        # delete text files
        shutil.rmtree(datadir.parent, ignore_errors=True)

    return True
