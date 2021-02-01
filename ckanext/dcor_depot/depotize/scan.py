import functools
import json
import pathlib
from pkg_resources import resource_filename
import re
import sys
import time

from dclab.rtdc_dataset import fmt_tdms

#: Files that belong to a measurement but must be copied,
#: because there is no equivalent in the .rtdc file format
#: (e.g. background images).
FILES_COPY_SUFFIX = [
    ".bmp",
    ".png",
    ".tif",
]


def find_rtdc_data(path):
    """Recursively return all RT-DC measurements

    (.rtdc and .tdms files)
    """
    rtdc = [r for r in path.rglob("*.rtdc") if r.is_file()]
    tdms = fmt_tdms.get_tdms_files(path)
    return rtdc + tdms


def find_associates(path, json_resource):
    """Returns list of paths associated with a measurement"""
    # Name list of files commonly associated with the file formats
    names_templates = load_json_resource(json_resource)
    associates = []
    # measurement identifier
    mid = path.name.split("_")[0].strip("Mm")
    names = []
    if mid:
        for name in names_templates:
            name = name.format(RUN=mid, STEM=path.stem)
            if name.count("*"):
                candidates = list(path.parent.glob(name))
                if len(candidates) > 1:
                    raise ValueError("Too many file candidates "
                                     "for '{}' in '{}'!".format(name, path))
                elif candidates:
                    name = candidates[0].name
                else:
                    continue
            names.append(name)
    for name in names:
        pp = path.with_name(name)
        if pp.exists():
            associates.append(pp)
    return associates


@functools.lru_cache()
def load_json_resource(resource):
    path = resource_filename("ckanext.dcor_depot.depotize", resource)
    with pathlib.Path(path).open() as fd:
        data = json.load(fd)
    return data


def scan(path, verbose=1):
    """Scan directory tree and return number of measurements/junk/unsorted"""
    path = pathlib.Path(path)

    # load json data
    scan_ign = load_json_resource("scan_ignore.json")

    t_start = time.time()
    #: List of empty directories (can be removed)
    empty_dirs = []
    #: Measurement data. Keys are tdms/rtdc files and values are
    #: all files related to this measurement.
    measurements = {}
    #: Excluded measurements (due to ambiguities in the data)
    measurements_excl = {}
    #: Additional data that should be copied over when converting
    #: tdms data (or when moving rtdc data); keys are tdms/rtdc paths
    #: and values are paths to additional files.
    copy_data = {}
    #: List of files that have no value or contain unusable data
    ignored = []
    #: Initially, this list is populated with all filenames. As
    #: the other lists/dicts are populated, this list is
    #: depopulated, yielding all unsorted files (python scripts,
    #: executables, etc.). Ideally, the list is empty after the scan.
    #: If this is not the case, a human should have a look.
    filelist = []

    # populate `filelist` and `ignored`
    ignore_file_regexp = [re.compile(fn) for fn in scan_ign["filenames"]]

    for ff in list(path.rglob("*")):
        if ff.is_dir():
            # ignore directories
            if len(list(ff.glob("*"))) == 0:
                # keep track of empty directories
                empty_dirs.append(ff)
        elif sum([bool(p.match(ff.name)) for p in ignore_file_regexp]):
            # ignore file names
            ignored.append(ff)
        elif sum([f.name.lower() in scan_ign["folders"] for f in ff.parents]):
            # ignored parent folders
            ignored.append(ff)
        else:
            filelist.append(ff)

    data = find_rtdc_data(path)

    # depopulate `filelist` (reflecting content in `data`),
    # cleanup `data` (remove ignored files and folders),
    # and populate `copy_data`.
    for pp in data:
        if pp not in filelist:
            # ignored data
            continue
        filelist.remove(pp)
        # 1st test: TDMS Measurement has exactly one set of data files
        try:
            if pp.suffix == ".tdms":
                # look for files associated with tdms data
                ppass = find_associates(pp, "scan_associate_tdms.json")
            else:
                ppass = []
        except ValueError:
            measurements_excl[pp] = "Ambiguous associate files"
            continue
        else:
            # 2nd test: No other TDMS measurement has same data files
            for pa in ppass:
                try:
                    # File has already been removed
                    # (is part of another measurement)
                    filelist.remove(pa)
                except ValueError:
                    if pa in ignored:
                        # An ignore-filter prematurely filtered out this
                        # file (could be e.g. a txt file).
                        ignored.remove(pa)
                        continue
                    # This might happen when a user records multiple
                    # measurements with different flow rates and does not
                    # increment the flow rate in Shape-In.
                    message = "Two or more measurements use {}".format(pa)
                    measurements_excl[pp] = message
                    # Also remove this item from already used measurements
                    for pm in list(measurements.keys()):
                        if pa in measurements[pm]:
                            measurements.pop(pm)
                            measurements_excl[pm] = message
                    break
            else:
                # clean measurement (at least until now)
                measurements[pp] = ppass
                # add associated files
                if pp.suffix == ".tdms":
                    # look for files associated with tdms data
                    ass = find_associates(pp, "scan_ancillaries_tdms.json")
                else:
                    ass = find_associates(pp, "scan_ancillaries_hdf5.json")
                copy_data[pp] = ass
                for af in ass:
                    # There may be cases where an ancillary file is shared
                    # by multiple measurements (e.g. in some cases there
                    # are additional measurement files that were somehow
                    # modified with AIDeveloper).
                    if af in filelist:
                        filelist.remove(af)

    # populate `copy_data` with remaining files from `filelist`
    # (get all additional files that should be copied)
    for pc in list(filelist):
        if pc.suffix.lower() in FILES_COPY_SUFFIX:
            # list of measurements that are related to this file
            rmcp = False
            refd = find_rtdc_data(pc.parent)
            for rr in refd:
                if rr not in copy_data:
                    copy_data[rr] = []
                copy_data[rr].append(pc)
                rmcp = True
            if rmcp:
                # Only remove if it is part of a measurement
                filelist.remove(pc)

    # results directory
    pout = path.parent

    # It is possible to manually acknowledge unknown files by copying
    # "unsorted.txt" to "unsorted_acknowledged.txt". This makes it
    # possible to start conversion without the "--ignore-unknown" flag.
    usrt_ack = pathlib.Path(pout / "unsorted_acknowledged.txt")
    if usrt_ack.exists():
        usrt_list = usrt_ack.read_text().split("\n")
        for pp in usrt_list:
            pp = pathlib.Path(pp)
            # remove any file that the user manually added
            if pp in filelist:
                filelist.remove(pp)
    else:
        usrt_list = []

    # show summary
    scan_info = {
        "duration [min]": (time.time() - t_start) / 60,
        "datasets": len(measurements),
        "datasets with ancillaries": len(copy_data),
        "datasets excluded": len(measurements_excl),
        "files ignored": len(ignored),
        "directories empty": len(empty_dirs),
        "files unknown": len(filelist),
        "files unknown acknowledged": len(usrt_list),
        }

    scan_lists = {
        "datasets": measurements,
        "datasets with ancillaries": copy_data,
        "datasets excluded": measurements_excl,
        "files ignored": ignored,
        "directories empty": empty_dirs,
        "files unknown": filelist,
    }

    if verbose >= 2:
        for key in scan_info:
            print("{}: {}".format(key, scan_info[key]))

    # save results
    with open(pout / "summary.txt", "w") as fd:
        for key in scan_info:
            fd.write("{}: {}\n".format(key, scan_info[key]))

    with open(pout / "measurements.txt", "w") as fd:
        for ms in measurements:
            if ms in copy_data:
                cd = "\t" + "\t".join(["{}".format(mi)
                                       for mi in copy_data[ms]])
            else:
                cd = ""
            try:
                fd.write("{}{}\n".format(ms, cd))
            except UnicodeEncodeError:
                print(ascii("Bad file name: {}".format(ms)))

    with open(pout / "measurements_excl.txt", "w") as fd:
        for ms in measurements_excl:
            fd.write("{}\t{}\n".format(ms, measurements_excl[ms]))

    with open(pout / "unsorted.txt", "w") as fd:
        for us in filelist:
            fd.write("{}\n".format(us))

    return scan_info, scan_lists


if __name__ == "__main__":
    scan(sys.argv[-1], verbose=1)
