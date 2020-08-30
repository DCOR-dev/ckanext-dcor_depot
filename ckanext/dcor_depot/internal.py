"""Import from internal location"""
import cgi
import json
import mimetypes
import os
import pathlib
import shutil
import tempfile

from ckan import logic

import dclab


from .orgs import INTERNAL_ORG
from .paths import INTERNAL_DEPOT, get_resource_path
from .depot import DUMMY_BYTES, make_id


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
    with sha256path.open("r") as fd:
        sums = fd.read().split("\n")
    for line in sums:
        line = line.strip()
        ss, name = line.split("  ")
        if name == path.name:
            return ss
    else:
        raise ValueError("Could not find sha256 sum for {}!".format(path))


def import_dataset(sha256_path):
    # determine all relevant resources
    root = sha256_path.parent
    files = sorted(root.glob(sha256_path.name.split(".")[0]+"*"))

    for ff in files:
        if ff.name.count("_condensed"):
            fc = ff
            break
    else:
        raise ValueError("No condensed file for {}!".format(sha256_path))

    files = [ff for ff in files if not ff.name.count("_condensed")]
    files = [ff for ff in files if not ff.suffix == ".sha256sums"]

    for ff in files:
        if ff.suffix == ".rtdc":
            break
    else:
        raise ValueError("No dataset file for {}!".format(sha256_path))

    # create the dataset
    dcor_dict = make_dataset_dict(ff)

    package_show = logic.get_action("package_show")
    package_create = logic.get_action("package_create")
    try:
        package_show(context=admin_context(),
                     data_dict={"id": dcor_dict["name"]})
    except logic.NotFound:
        package_create(context=admin_context(), data_dict=dcor_dict)
    else:
        print("Skipping creation of {} (exists)".format(dcor_dict["name"]))

    resource_show = logic.get_action("resource_show")
    resource_create = logic.get_action("resource_create")
    rmid = make_id([dcor_dict["id"], ff.name, load_sha256sum(ff)])
    try:
        resource_show(context=admin_context(), data_dict={"id": rmid})
    except logic.NotFound:
        tmp = tempfile.mkdtemp(prefix="import_")

        # make link to condensed  before importing the resource
        # (to avoid conflicts with automatic generation of condensed file)
        rmpath = get_resource_path(rmid, create_dirs=True)
        rmpath_c = rmpath + "_condensed.rtdc"
        if not os.path.exists(rmpath_c):
            os.symlink(str(fc), rmpath_c)

        # import the resources
        for path in files:
            print("  - importing {}".format(path))
            # use dummy file (workaround for MemoryError during upload)
            upath = os.path.join(tmp, path.name)
            with open(upath, "wb") as fd:
                fd.write(DUMMY_BYTES)
            shasum = load_sha256sum(path)
            with open(upath, "rb") as fd:
                # This is a kind of hacky way of tricking CKAN into thinking
                # that there is a file upload.
                upload = cgi.FieldStorage()
                upload.filename = path.name  # used in ResourceUpload
                upload.file = fd  # used in ResourceUpload
                upload.list.append(None)  # for boolean test in ResourceUpload
                rs = resource_create(
                    context=admin_context(),
                    data_dict={
                        "id": make_id([dcor_dict["id"],
                                       path.name,
                                       load_sha256sum(path)]),
                        "package_id": dcor_dict["name"],
                        "upload": upload,
                        "name": path.name,
                        "sha256": shasum,
                        "size": path.stat().st_size,
                        "format": mimetypes.guess_type(str(path))[0],
                    }
                )
            rpath = get_resource_path(rs["id"])
            os.remove(rpath)
            os.symlink(str(path), rpath)

        # cleanup
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("Skipping resource import for dataset {} (exist)".format(
            dcor_dict["name"]))


def internal(limit=0):
    """Import internal datasets"""
    # prerequisites
    create_internal_org()

    # iterate through all files
    ii = 0
    for ppsha in pathlib.Path(INTERNAL_DEPOT).rglob("*.sha256sums"):
        ii += 1
        import_dataset(ppsha)
        if limit and ii >= limit:
            break


def make_dataset_dict(path):
    dcor = {}
    dcor["owner_org"] = INTERNAL_ORG
    dcor["private"] = True
    dcor["license_id"] = "none"
    stem = "_".join(path.name.split("_")[:3])
    dcor["name"] = stem
    dcor["state"] = "active"
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
