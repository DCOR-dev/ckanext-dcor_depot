import pathlib
import sys
import time

from dclab.rtdc_dataset import new_dataset, check_dataset, fmt_tdms
import numpy as np


def date2datelist(date):
    """Converts a date in the form YYYY-MM-DD to common folder names"""
    dlist = [
        date,
        date.replace("-", ""),
        date.replace("-", "")[2:],
    ]
    return dlist


def use_wrong_event_count(viol, dmin=-10, dmax=np.inf):
    """Decide whether to include measurements with missing image/contour"""
    use = True
    for v in viol:
        diff = event_count_difference(v)
        if diff < dmin or diff > dmax:
            use = False
            break
    return use


def event_count_difference(v):
    """negative means that feature is missing events"""
    if v.startswith("Features: wrong event count: '"):
        ofstr = v.split(":")[2]
        ll, rr = ofstr.split(" of ")
        ll = int(ll.split("(")[1])
        rr = int(rr.split(")")[0])
        diff = ll - rr
    else:
        # dummy
        diff = 0
    return diff


def check(pathtxt, verbose=1):
    pathtxt = pathlib.Path(pathtxt)
    if not pathtxt.name == "measurements.txt":
        raise ValueError("Please specify a 'measurements.txt' file!")

    t0 = time.time()
    data = pathtxt.read_text().split("\n")
    violations = {}
    alerts = {}
    information = {}
    timefaults = []
    invalid = []
    usable = []
    expected = {
        # Alerts
        # cannot be guessed
        "Metadata: Missing key [setup] 'flow rate sample'": [],
        # cannot be guessed
        "Metadata: Missing key [setup] 'flow rate sheath'": [],
        # only for newer setups
        "Metadata: Missing key [setup] 'identifier'": [],
        # only for newer setups
        "Metadata: Missing key [setup] 'module composition'": [],
        # will be added when tdms2rtdc is run
        "Metadata: Missing key [fluorescence] 'channel count'": [],
        "Metadata: Missing key [fluorescence] 'samples per event'": [],
        "Metadata: Missing key [setup] 'temperature', because the 'temp' " \
        + "feature is given": [],
        # Violations
        # only for newer setups
        "Metadata: Missing key [setup] 'medium'": [],
        # Wrong event count collection
        "Features: wrong event count abs(diff) < 5": [],
    }

    for line in data:
        if line.strip():
            path = line.split("\t")[0]
            try:
                ds = new_dataset(path)
                if len(ds) < 50:
                    # exclude short measurements
                    invalid.append(path)
                    continue
                else:
                    viol, aler, info = check_dataset(ds)
                    # determine data and check against folder name
                    date = ds.config["experiment"]["date"]
            except (fmt_tdms.InvalidTDMSFileFormatError,
                    fmt_tdms.IncompleteTDMSFileFormatError,
                    fmt_tdms.event_contour.ContourIndexingError,
                    fmt_tdms.event_image.InvalidVideoFileError):
                invalid.append(path)
                continue
            except BaseException:
                if verbose >= 1:
                    print("!!! OTHER PROBELM WITH {}".format(path))
                invalid.append(path)
                continue
            finally:
                # finally is always called (even if continue is used)
                try:
                    ds.__exit__(None, None, None)
                except BaseException:
                    pass
            if not use_wrong_event_count(viol):
                if verbose >= 1:
                    print("!!! Excluded due to bad event counts: {}".format(
                        path))
                invalid.append(path)
                continue
            for v in viol:
                if v in expected:
                    expected[v].append(path)
                elif abs(event_count_difference(v)) < 5:
                    expkey = "Features: wrong event count abs(diff) < 5"
                    expected[expkey].append(path)
                else:
                    if verbose >= 2:
                        print("{}: {}".format(v, path))
                    if v not in violations:
                        violations[v] = []
                    violations[v].append(path)
            for a in aler:
                if a in expected:
                    expected[a].append(path)
                else:
                    if a not in alerts:
                        alerts[a] = []
                    alerts[a].append(a)
            for i in info:
                if i not in information:
                    information[i] = []
                information[i].append(path)
            for dd in date2datelist(date):
                if dd in str(path):
                    break
            else:
                timefaults.append([date, path])
            # if we got here, we can at least use the data
            usable.append(line)

    if verbose >= 2:
        print("Check took {:.0f} mins.".format((time.time() - t0) / 60))

    with pathtxt.with_name("check_info.txt").open("w") as fd:
        for ik in sorted(information.keys()):
            fd.write("[{}x]\t{}\n".format(len(information[ik]), ik))

    with pathtxt.with_name("check_alerts.txt").open("w") as fd:
        for ik in sorted(alerts.keys()):
            fd.write("[{}x]\t{}\n".format(len(alerts[ik]), ik))
            for pal in alerts[ik]:
                fd.write("{}\n".format(pal))
            fd.write("\n")

    with pathtxt.with_name("check_violations.txt").open("w") as fd:
        for ik in sorted(violations.keys()):
            fd.write("[{}x]\t{}\n".format(len(violations[ik]), ik))
            for pvi in violations[ik]:
                fd.write("{}\n".format(pvi))
            fd.write("\n")

    with pathtxt.with_name("check_times.txt").open("w") as fd:
        for dd in timefaults:
            fd.write("[{}]\t{}\n".format(dd[0], dd[1]))

    with pathtxt.with_name("check_invalid.txt").open("w") as fd:
        for pp in invalid:
            fd.write("{}\n".format(pp))

    with pathtxt.with_name("check_usable.txt").open("w") as fd:
        for pp in usable:
            fd.write("{}\n".format(pp))

    with pathtxt.with_name("check_expected_problems.txt").open("w") as fd:
        for ik in sorted(expected.keys()):
            fd.write("[{}x]\t{}\n".format(len(expected[ik]), ik))
            for pvi in expected[ik]:
                fd.write("{}\n".format(pvi))
            fd.write("\n")

    check_results = {
        "alerts": alerts,
        "information": information,
        "invalid": invalid,
        "usable": usable,
        "violations": violations,
    }
    return check_results


if __name__ == "__main__":
    check(sys.argv[-1], verbose=1)
