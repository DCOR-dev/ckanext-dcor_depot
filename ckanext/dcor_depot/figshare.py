"""Import predefined datasets from figshare.com"""
import cgi
import grp
import mimetypes
import os
import pathlib
import pkg_resources
import pwd
import shutil
import tempfile

from ckan import logic

from dcor_shared import get_resource_path
from html2text import html2text
import requests

from .depot import DUMMY_BYTES, make_id, sha_256
from .orgs import FIGSHARE_ORG
from .paths import FIGSHARE_DEPOT
from .util import check_md5


FIGSHARE_BASE = "https://api.figshare.com/v2"


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def create_figshare_org():
    """Creates a CKAN organization (home of all linked figshare data)"""
    organization_show = logic.get_action("organization_show")
    organization_create = logic.get_action("organization_create")
    # check if organization exists
    try:
        organization_show(context=admin_context(),
                          data_dict={"id": FIGSHARE_ORG})
    except logic.NotFound:
        # create user
        data_dict = {
            "name": FIGSHARE_ORG,
            "description": u"This lab contains selected data imported from "
            + u"figshare. If you would like your dataset to appear "
            + u"here, please send the figshare DOI to Paul Müller.",
            "title": "Figshare mirror"
        }
        organization_create(context=admin_context(),
                            data_dict=data_dict)


def download_file(url, path):
    """Download (large) file without big memory footprint"""
    path = pathlib.Path(path)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with path.open('wb') as fd:
            for chunk in r.iter_content(chunk_size=8192):
                fd.write(chunk)


def figshare(limit=0):
    """Import all datasets in figshare_links.txt"""
    # prerequisites
    create_figshare_org()
    # use pkg_resources to get list of figshare DOIs
    doifile = pkg_resources.resource_filename("ckanext.dcor_depot",
                                              "figshare_dois.txt")
    # import datasets
    with open(doifile, "r") as fd:
        dois = [f.strip() for f in fd.readlines() if f.strip()]

    if limit != 0:
        dois = dois[:limit]

    for doi in dois:
        import_dataset(doi)


def import_dataset(doi):
    # Convert DOI to url
    uid = doi.split(".")[-2]
    ver = doi.split(".")[-1].strip("v ")
    url = "{}/articles/{}/versions/{}".format(FIGSHARE_BASE, uid, ver)
    # Get the JSON representation of the metadata
    req = requests.get(url)
    if not req.ok:
        raise ConnectionError("Error accessing {}: {}".format(
            url, req.reason))
    figshare_dict = req.json()
    # Convert the dictionary to DCOR and create draft
    dcor_dict = map_figshare_to_dcor(figshare_dict)

    package_show = logic.get_action("package_show")
    package_create = logic.get_action("package_create")
    try:
        package_show(context=admin_context(),
                     data_dict={"id": dcor_dict["name"]})
    except logic.NotFound:
        package_create(context=admin_context(), data_dict=dcor_dict)
    else:
        print("Skipping creation of {} (exists)".format(dcor_dict["name"]))

    # Download/Import the resources
    dldir = pathlib.Path(FIGSHARE_DEPOT) / dcor_dict["name"]
    dldir.mkdir(parents=True, exist_ok=True)

    resource_create = logic.get_action("resource_create")
    for res in figshare_dict["files"]:
        if not res["is_link_only"]:
            # check if resource exists
            pkg = package_show(context=admin_context(),
                               data_dict={"id": dcor_dict["name"]})
            names = [r["name"] for r in pkg["resources"]]
            if res["name"] in names:
                print("Resource {} exists.".format(res["name"]))
                continue
            # Download/Verify resource
            dlpath = dldir / res["name"]
            if dlpath.exists():
                try:
                    check_md5(dlpath, res["supplied_md5"])
                except ValueError:
                    download_file(res["download_url"], dlpath)
                else:
                    print("Using existing {}...".format(dlpath))
            else:
                print("Downloading {}...".format(res["name"]))
                download_file(res["download_url"], dlpath)
            check_md5(dlpath, res["supplied_md5"])

            # use dummy file (workaround for MemoryError during upload)
            tmp = pathlib.Path(tempfile.mkdtemp(prefix="dummy_"))
            upath = tmp / res["name"]
            with upath.open("wb") as fd:
                fd.write(DUMMY_BYTES)
            with upath.open("rb") as fd:
                # This is a kind of hacky way of tricking CKAN into thinking
                # that there is a file upload.
                upload = cgi.FieldStorage()
                upload.filename = res["name"]  # used in ResourceUpload
                upload.file = fd  # used in ResourceUpload
                upload.list.append(None)  # for boolean test in ResourceUpload
                rs = resource_create(
                    context=admin_context(),
                    data_dict={
                        "id": make_id([dcor_dict["id"], res["supplied_md5"]]),
                        "package_id": dcor_dict["name"],
                        "upload": upload,
                        "name": res["name"],
                        "sha256": sha_256(dlpath),
                        "size": dlpath.stat().st_size,
                        "format": mimetypes.guess_type(dlpath)[0],
                    }
                )
            shutil.rmtree(tmp, ignore_errors=True)
            # create file system link to downloaded file
            rpath = get_resource_path(rs["id"])
            rpath.unlink()
            rpath.symlink_to(dlpath)
            # make www-data the owner of the resource
            www_uid = pwd.getpwnam("www-data").pw_uid
            www_gid = grp.getgrnam("www-data").gr_gid
            os.chown(rpath.parent, www_uid, www_gid)
            os.chown(rpath.parent.parent, www_uid, www_gid)
    # activate the dataset
    package_revise = logic.get_action("package_revise")
    package_revise(context=admin_context(),
                   data_dict={"match": {"id": dcor_dict["id"]},
                              "update": {"state": "active"}})
    print("Done.")


def map_figshare_to_dcor(figs):
    """Convert figshare metadata to DCOR/CKAN metadata"""
    dcor = {}
    dcor["owner_org"] = FIGSHARE_ORG
    dcor["private"] = False
    reflist = []
    for item in figs["references"]:
        if item.count("://"):
            reflist.append(item)
        else:
            reflist.append("doi:{}".format(item))
    dcor["references"] = ", ".join(reflist)
    if figs["license"]["name"] == "CC0":
        dcor["license_id"] = "CC0-1.0"
    else:
        raise ValueError("Unknown license: {}".format(figs["license"]))
    dcor["title"] = figs["title"]
    dcor["state"] = "draft"
    author_list = []
    for item in figs["authors"]:
        author_list.append(item["full_name"])
    dcor["authors"] = ", ".join(author_list)
    dcor["doi"] = figs["doi"]
    dcor["name"] = "figshare-{}-v{}".format(figs["id"], figs["version"])
    dcor["organization"] = {"id": FIGSHARE_ORG}
    # markdownify and remove escapes "\_" with "_" (figshare-7771184-v2)
    dcor["notes"] = html2text(figs["description"]).replace("\_",  # noqa: W605
                                                           "_")
    dcor["id"] = make_id([dcor["doi"], dcor["name"]])
    return dcor
