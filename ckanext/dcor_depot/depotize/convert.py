import json
import hashlib
import pathlib
import shutil
import sys
import warnings

import dclab
from dclab import cli
from dclab.rtdc_dataset import fmt_tdms
from dclab.rtdc_dataset.export import LimitingExportSizeWarning
import h5py


if __name__ == "__main__":
    # allow to be run as script for testing
    _pathtxt = pathlib.Path(sys.argv[-1])
    assert _pathtxt.exists()
    INTERNAL_DEPOT = str(_pathtxt.parent / "internal")
    version = "test"
else:
    from ..paths import INTERNAL_DEPOT
    from .._version import version


DATA_DIR = INTERNAL_DEPOT + "/{YYY}X/{YYYY}-{MM}/{DD}"
NAME_STEM = "{YYYY}-{MM}-{DD}_{t}_{hex}"


def convert(pathtxt, verbose=1):
    pathtxt = pathlib.Path(pathtxt)
    if not pathtxt.name == "check_usable.txt":
        raise ValueError("Please specify a 'check_usable.txt' file!")

    data = pathtxt.read_text().split("\n")
    length = len(data)
    unused = []

    for ii, line in enumerate(data):
        if verbose >= 1:
            progr = "Converting: {:.2f}%".format(ii/length*100)
            if verbose >= 2:
                progr += ": {}".format(line.split("\t")[0])
            print(progr, end="\r")
        line = line.strip()
        if line:
            files = [pathlib.Path(ff) for ff in line.split("\t")]
            relp = pathtxt.parent / "data"
            hash0 = sha256(files[0])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with dclab.new_dataset(files[0]) as ds:
                    # get date and time
                    date = ds.config["experiment"]["date"]
                    year, month, day = date.split("-")
                    mtime = ds.config["experiment"]["time"].replace(":", "")
            ddir = pathlib.Path(DATA_DIR.format(YYY=year[:3],
                                                YYYY=year,
                                                MM=month,
                                                DD=day))
            ddir.mkdir(parents=True, exist_ok=True)
            stem = NAME_STEM.format(YYYY=year,
                                    MM=month,
                                    DD=day,
                                    t=mtime[:4],
                                    hex=hash0[:6])

            sha256sums = {}
            path_out = ddir / (stem + "_v1.rtdc")
            path_out_cond = ddir / (stem + "_v1_condensed.rtdc")
            path_sums = ddir / (stem + ".sha256sums")

            # This is just a simple test whether the dataset already exists.
            # It probably needs to be refined once there are "_v2" files?
            if path_sums.exists():
                # This file is created in the end. Thus, checking for this
                # file is the safest way of knowing that the conversion
                # succeeded before.
                continue
            else:
                # remove all other files from a previous, incomplete run
                delete_stem(ddir, stem)
            # Copy additional files
            dcor_hist = cli.get_job_info()
            dcor_hist["ckanext.dcor_depot"] = version

            dcor_hist["origin"] = {"path": str(files[0].relative_to(relp)),
                                   "hash": hash0}
            copyfiles = []
            if len(files) > 1:
                adfiles = sorted(files[1:], key=lambda p: p.name.lower())
                for jj, ff in enumerate(adfiles):
                    adi = (stem + "_ad{}_{}".format(jj + 1, ff.name.lower()))
                    cpp = ddir / adi
                    shutil.copyfile(ff, cpp)
                    sha256sums[adi] = sha256(cpp)
                    copyfiles.append({"index": jj + 1,
                                      "path": str(ff.relative_to(relp)),
                                      "hash": sha256(ff),
                                      "name": adi,
                                      })
            if copyfiles:
                dcor_hist["additional files"] = copyfiles
            # Generate rtdc file
            if files[0].suffix.lower() == ".rtdc":
                try:
                    cli.compress(path_out=path_out, path_in=files[0])
                except KeyboardInterrupt:
                    sys.exit(1)
                except BaseException:
                    delete_stem(ddir, stem)
                    if verbose >= 1:
                        print("!! Problem compressing {}".format(files[0]))
                    unused.append(files[0])
                    continue
            else:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore',
                                              LimitingExportSizeWarning)
                        cli.tdms2rtdc(path_tdms=files[0],
                                      path_rtdc=path_out,
                                      compute_features=False,
                                      verbose=False)
                except fmt_tdms.event_contour.ContourIndexingError:
                    delete_stem(ddir, stem)
                    if verbose >= 1:
                        print(
                            "!! ContourIndexingError for {}".format(files[0]))
                    unused.append(files[0])
                    continue
                except KeyboardInterrupt:
                    sys.exit(1)
                except BaseException:
                    delete_stem(ddir, stem)
                    if verbose >= 1:
                        print("!! OTHER ERROR for {}".format(files[0]))
                    unused.append(files[0])
                    continue
            # append dcor history log file
            dcdump = {"v1": dcor_hist}
            dclog = json.dumps(dcdump, sort_keys=True, indent=2).split("\n")
            with h5py.File(path_out, "a") as h5:
                dclab.rtdc_dataset.write(path_or_h5file=h5,
                                         logs={"dcor-history": dclog},
                                         mode="append")
            # condense path_out to path_out_min
            try:
                cli.condense(path_out=path_out_cond, path_in=path_out)
            except KeyboardInterrupt:
                sys.exit(1)
            except BaseException:
                delete_stem(ddir, stem)
                if verbose >= 1:
                    print("!! Condensing Error for {}".format(files[0]))
                unused.append(files[0])
                continue
            # compute sha256 sums
            sha256sums[path_out.name] = sha256(path_out)
            sha256sums[path_out_cond.name] = sha256(path_out_cond)
            with open(path_sums, "w") as fd:
                for kk in sorted(sha256sums.keys()):
                    fd.write("{}  {}\n".format(sha256sums[kk], kk))
    # Write unused files
    with pathtxt.with_name("convert_excluded.txt").open("w") as fd:
        fd.writelines([str(f)+"\n" for f in unused])
    if verbose >= 2:
        print("Converting: 100% Done. ")


def delete_stem(ddir, stem):
    """Delete all files starting with `stem` in directory `ddir`"""
    delfiles = ddir.glob(stem+"*")
    for df in delfiles:
        df.unlink()


def sha256(path):
    return dclab.util.hashfile(path, constructor=hashlib.sha256)


if __name__ == "__main__":
    convert(sys.argv[-1])
