"""Import from internal location"""
import cgi
import datetime
import grp
import json
import mimetypes
import os
import pathlib
import pwd
import shutil
import sys
import tempfile

from ckan import logic

import dclab
from dclab import cli
from dcor_shared import get_resource_path

from .orgs import INTERNAL_ORG
from .paths import INTERNAL_DEPOT
from .depot import DUMMY_BYTES, make_id, sha_256


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def create_internal_org():
    """Creates a CKAN organization (home of all linked data)"""
    organization_show = logic.get_action("organization_show")
    organization_create = logic.get_action("organization_create")
    # check if organization exists
    try:
        organization_show(context=admin_context(),
                          data_dict={"id": INTERNAL_ORG})
    except logic.NotFound:
        # create user
        data_dict = {
            "name": INTERNAL_ORG,
            "description": u"Internal/archived datasets of the Guck "
                           + u"division. All datasets are private. If you are "
                           + u"missing a dataset, please contact Paul Müller.",
            "title": "Guck Division Archive"
        }
        organization_create(context=admin_context(),
                            data_dict=data_dict)


def load_sha256sum(path):
    stem = "_".join(path.name.split("_")[:3])
    sha256path = path.with_name(stem + ".sha256sums")
    try:
        sums = sha256path.read_text().split("\n")
    except UnicodeDecodeError:
        print("DAMN! Bad character in {}!".format(sha256path))
        raise
    for line in sums:
        line = line.strip()
        if line:
            ss, name = line.split("  ", 1)
            if name == path.name:
                return ss
    else:
        raise ValueError("Could not find sha256 sum for {}!".format(path))


def import_dataset(sha256_path):
    """Import a dataset (all resources in sha256_path are added)"""
    # determine all relevant resources
    root = sha256_path.parent
    files = sorted(root.glob(sha256_path.name.split(".")[0] + "*"),
                   # rtdc files should come first
                   key=(lambda p: "0000" + p.name
                        if p.suffix == ".rtdc" else p.name))

    for ff in files:
        if ff.name.count("_condensed"):
            condensed_depot_path = ff
            break
    else:
        raise ValueError("No condensed file for {}!".format(sha256_path))

    if len(files) > 50:
        raise ValueError("Found too many ({}) files for {}!".format(
            len(files), sha256_path))

    files = [ff for ff in files if not ff.name.count("_condensed")]
    files = [ff for ff in files if not ff.suffix == ".sha256sums"]

    for ff in files:
        if ff.suffix == ".rtdc":
            resource_depot_path = ff
            break
    else:
        raise ValueError("No dataset file for {}!".format(sha256_path))

    # create the dataset
    dataset_dict = make_dataset_dict(resource_depot_path)

    package_show = logic.get_action("package_show")
    package_create = logic.get_action("package_create")
    try:
        package_show(context=admin_context(),
                     data_dict={"id": dataset_dict["name"]})
    except logic.NotFound:
        package_create(context=admin_context(), data_dict=dataset_dict)
    else:
        print("Skipping creation of {} (exists) ".format(dataset_dict["name"]),
              end="\r")

    # Obtain the .rtdc resource identifier
    rtdc_id = make_id([dataset_dict["id"],
                       resource_depot_path.name,
                       load_sha256sum(resource_depot_path)])

    resource_show = logic.get_action("resource_show")
    try:
        resource_show(context=admin_context(), data_dict={"id": rtdc_id})
    except logic.NotFound:
        # make link to condensed  before importing the resource
        # (to avoid conflicts with automatic generation of condensed file)
        import_rtdc_prepare_condensed(rtdc_id, condensed_depot_path)
        # import all resources (except the condensed and sha256sum file)
        for path in files:
            import_resource(dataset_dict,
                            resource_depot_path=path,
                            sha256_sum=load_sha256sum(path))
    else:
        print("Skipping resource for {} (exists)".format(
            dataset_dict["name"]), end="\r")
    # activate the dataset
    package_revise = logic.get_action("package_revise")
    package_revise(context=admin_context(),
                   data_dict={"match": {"id": dataset_dict["id"]},
                              "update": {"state": "active"}})


def import_rtdc_prepare_condensed(rtdc_id, condensed_depot_path):
    """
    Create a link to the condensed file before importing any resources
    (to avoid conflicts with automatic generation of condensed file)
    """
    rmpath = get_resource_path(rtdc_id, create_dirs=True)
    # This path should not exist (checked above)
    rmpath_c = rmpath.with_name(rmpath.name + "_condensed.rtdc")
    assert not rmpath_c.exists(), "Should not exist: {}".format(rmpath_c)
    rmpath_c.symlink_to(condensed_depot_path)


def import_resource(dataset_dict, resource_depot_path, sha256_sum):
    """Import a resource into a dataset

    There is no internal upload happening, only a symlink to
    `resource_depot_path` is created. The `sha256_sum` of the
    `resource_depot_path` is necessary for reproducible resource
    ID generation.
    """
    path = resource_depot_path
    resource_create = logic.get_action("resource_create")
    # import the resources
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="import_"))
    print("  - importing {}".format(path))
    # use dummy file (workaround for MemoryError during upload)
    upath = tmp / path.name
    with upath.open("wb") as fd:
        fd.write(DUMMY_BYTES)
    with upath.open("rb") as fd:
        # This is a kind of hacky way of tricking CKAN into thinking
        # that there is a file upload.
        upload = cgi.FieldStorage()
        upload.filename = path.name  # used in ResourceUpload
        upload.file = fd  # used in ResourceUpload
        upload.list.append(None)  # for boolean test in ResourceUpload
        rs = resource_create(
            context=admin_context(),
            data_dict={
                "id": make_id([dataset_dict["id"],
                               path.name,
                               sha256_sum]),
                "package_id": dataset_dict["name"],
                "upload": upload,
                "name": path.name,
                "sha256": sha256_sum,
                "size": path.stat().st_size,
                "format": mimetypes.guess_type(str(path))[0],
            }
        )
    rpath = get_resource_path(rs["id"])
    rpath.unlink()
    rpath.symlink_to(path)
    # make www-data the owner of the resource
    www_uid = pwd.getpwnam("www-data").pw_uid
    www_gid = grp.getgrnam("www-data").gr_gid
    os.chown(rpath.parent, www_uid, www_gid)
    os.chown(rpath.parent.parent, www_uid, www_gid)
    # cleanup
    shutil.rmtree(tmp, ignore_errors=True)


def internal(limit=0, start_date="2000-01-01", end_date="3000-01-01"):
    """Import all internal datasets

    Parameters
    ----------
    limit: int
        Limit the number of datasets to be imported; If set to 0
        (default), all datasets are imported.
    start_date: str
        Only import datasets in the depot at or after this date
        (format YYYY-MM-DD)
    end_date: str
        Only import datasets in the depot at or before this date
    """
    # prerequisites
    create_internal_org()
    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")

    # iterate through all files
    ii = 0
    for ppsha in pathlib.Path(INTERNAL_DEPOT).rglob("*.sha256sums"):
        # Check whether the date matches
        ppdate = datetime.datetime.strptime(ppsha.name[:10], "%Y-%m-%d")
        if start <= ppdate <= end:
            ii += 1
            import_dataset(ppsha)
            if limit and ii >= limit:
                break


def internal_upgrade(start_date="2000-01-01", end_date="3000-01-01"):
    """Add new resource versions to internal datasets

    Parameters
    ----------
    start_date: str
        Only import datasets in the depot at or after this date
        (format YYYY-MM-DD)
    end_date: str
        Only import datasets in the depot at or before this date
    """

    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")

    # iterate through all files
    for ppsha in pathlib.Path(INTERNAL_DEPOT).rglob("*.sha256sums"):
        # Check whether the date matches
        ppdate = datetime.datetime.strptime(ppsha.name[:10], "%Y-%m-%d")
        if start <= ppdate <= end:
            upgrade_dataset(ppsha)


def make_dataset_dict(path):
    dcor = {}
    dcor["owner_org"] = INTERNAL_ORG
    dcor["private"] = True
    dcor["license_id"] = "none"
    stem = "_".join(path.name.split("_")[:3])
    dcor["name"] = stem
    dcor["state"] = "draft"
    dcor["organization"] = {"id": INTERNAL_ORG}

    with dclab.new_dataset(path) as ds:
        # get the title from the logs
        log = "\n".join(ds.logs["dcor-history"])

    info = json.loads(log)
    op = info["v1"]["origin"]["path"]
    dirs = op.split("/")
    for string in ["Online", "Offline", "online", "offline"]:
        if string in dirs:
            dirs.remove(string)

    dirs[-1] = dirs[-1].rsplit(".", 1)[0]  # remove suffix
    dcor["title"] = " ".join([d.replace("_", " ") for d in dirs])
    # guess author
    dcor["authors"] = "unknown"

    dcor["notes"] = "The location of the original dataset is {}.".format(op)
    dcor["id"] = make_id([load_sha256sum(path), dcor["name"]])
    return dcor


def upgrade_dataset(sha256_path):
    root = sha256_path.parent
    # actual files present
    files_act = sorted(root.glob(sha256_path.name.split(".")[0] + "*"))
    files_act = [ff for ff in files_act if not ff.suffix == ".sha256sums"]
    # files registered in tha sha256sum
    files_reg = sorted([root / pp.split("  ", 1)[1] for pp in
                        sha256_path.read_text().split("\n") if pp])
    if files_act != files_reg:
        # find the new version
        for ff in files_act:
            if (ff.suffix == ".rtdc"
                    and not ff.name.count("condensed")
                    and ff not in files_reg):
                path_new = ff
                sha256_new = sha_256(ff)
                break
        else:
            raise ValueError(
                "Could not find new version for {}!".format(sha256_path))
        # first, create a condensed version
        path_cond = path_new.with_name(path_new.stem + "_condensed.rtdc")
        if path_cond.exists():
            print("Recreating condensed dataset {}".format(path_cond))
            path_cond.unlink()
        else:
            print("Creating condensed dataset {}".format(path_cond))

        try:
            cli.condense(path_out=path_cond, path_in=path_new)
        except BaseException:
            print("!! Condensing Error for {}".format(path_new))
            sys.exit(1)
        # now, append the resource to the dataset
        dataset_name = "_".join(path_new.name.split("_")[:3])
        package_show = logic.get_action("package_show")
        dataset_dict = package_show(context=admin_context(),
                                    data_dict={"id": dataset_name})

        resource_show = logic.get_action("resource_show")
        # Obtain the .rtdc resource identifier
        # (ID is independent of _v1 string)
        rtdc_id = make_id([dataset_dict["id"],
                           path_new.name,
                           sha256_new])
        try:
            resource_show(context=admin_context(), data_dict={"id": rtdc_id})
        except logic.NotFound:
            # make link to condensed  before importing the resource
            # (to avoid conflicts with automatic generation of condensed file)
            import_rtdc_prepare_condensed(rtdc_id, path_cond)
            # import the resource
            import_resource(dataset_dict,
                            resource_depot_path=path_new,
                            sha256_sum=sha256_new)
        else:
            print("Skipping resource for {} (exists)".format(
                dataset_dict["name"]), end="\r")

        # Now make the new resource the first resource in the dataset
        package_resource_reorder = logic.get_action("package_resource_reorder")
        package_resource_reorder(context=admin_context(),
                                 data_dict={"id": dataset_name,
                                            "order": [rtdc_id]})

        # Finally, compute the sha256 sums and add them to the sum file.
        sha256sums = {path_new.name: sha_256(path_new),
                      path_cond.name: sha_256(path_cond)}
        with sha256_path.open("r+") as fd:
            fd.seek(0, 2)  # seek to end of file
            for kk in sorted(sha256sums.keys()):
                fd.write("{}  {}\n".format(sha256sums[kk], kk))
