"""Import predefined datasets from figshare.com"""
import hashlib
import pathlib
import pkg_resources
import tempfile

from ckan import common, logic

from dcor_shared import s3
from html2text import html2text
import requests

from .app_res import admin_context, append_ckan_resource_to_active_dataset
from .util import check_md5, make_id


FIGSHARE_BASE = "https://api.figshare.com/v2"
FIGSHARE_ORG = "figshare-import"


def create_figshare_org():
    """Creates a CKAN organization (home of all linked figshare data)"""
    organization_show = logic.get_action("organization_show")
    organization_create = logic.get_action("organization_create")
    # check if organization exists
    try:
        org_dict = organization_show(context=admin_context(),
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
        org_dict = organization_create(context=admin_context(),
                                       data_dict=data_dict)
    return org_dict


def download_file(url, path, ret_sha256=False):
    """Download (large) file without big memory footprint"""
    if ret_sha256:
        hasher = hashlib.sha256()
    else:
        hasher = None
    path = pathlib.Path(path)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with path.open('wb') as fd:
            for chunk in r.iter_content(chunk_size=2**20):
                fd.write(chunk)
                if ret_sha256:
                    hasher.update(chunk)
    if ret_sha256:
        return hasher.hexdigest()
    else:
        return None


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
    url = f"{FIGSHARE_BASE}/articles/{uid}/versions/{ver}"
    # Get the JSON representation of the metadata
    req = requests.get(url)
    if not req.ok:
        raise ConnectionError(f"Error accessing {url}: {req.reason}")
    figshare_dict = req.json()
    # Convert the dictionary to DCOR and create draft
    ds_dict_figshare = map_figshare_to_dcor(figshare_dict)

    package_show = logic.get_action("package_show")
    package_create = logic.get_action("package_create")

    try:
        ds_dict = package_show(context=admin_context(),
                               data_dict={"id": ds_dict_figshare["name"]})
    except logic.NotFound:
        ds_dict = package_create(context=admin_context(),
                                 data_dict=ds_dict_figshare)
        assert ds_dict["id"] == ds_dict_figshare["id"]
    else:
        print(f"Skipping creation of {ds_dict['name']} (exists)")

    # Operate in a cache location
    cache_loc = common.config.get("ckanext.dcor_depot.tmp_dir")
    if not cache_loc:
        cache_loc = None
    else:
        # Make sure the directory exists and don't panic when we cannot
        # create it.
        try:
            pathlib.Path(cache_loc).mkdir(parents=True, exist_ok=True)
        except BaseException:
            cache_loc = None

    if cache_loc is None:
        cache_loc = tempfile.mkdtemp(prefix="ckanext-dcor_depot_")

    # Download/Import the resources
    for res in figshare_dict["files"]:
        if not res["is_link_only"]:
            rid = make_id([ds_dict["id"], res["supplied_md5"]])

            # Make sure the resource is on S3
            bucket_name = common.config[
                "dcor_object_store.bucket_name"].format(
                organization_id=ds_dict["organization"]["id"])
            object_name = f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}"
            if s3.object_exists(bucket_name=bucket_name,
                                object_name=object_name):
                print(f"Resource {res['name']} already on S3")
            else:
                # download to and/or verify on disk
                print(f"Downloading {res['name']}...")
                dlpath = pathlib.Path(cache_loc) / res["name"]
                sha256 = download_file(res["download_url"], dlpath,
                                       ret_sha256=True)
                check_md5(dlpath, res["supplied_md5"])

                # upload the resource to S3
                print(f"Uploading to S3 {res['name']}...")
                s3.upload_file(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    path=dlpath,
                    sha256=sha256,
                    private=ds_dict["private"],
                )

            # Make sure the resource is in the CKAN database
            append_ckan_resource_to_active_dataset(
                dataset_id=ds_dict["id"],
                res_dict={"id": rid,
                          "name": res["name"],
                          "s3_available": True,
                          }
            )

    # activate the dataset
    package_patch = logic.get_action("package_patch")
    package_patch(context=admin_context(),
                  data_dict={"id": ds_dict["id"],
                             "state": "active"})
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
            reflist.append(f"doi:{item}")
    dcor["references"] = ", ".join(reflist)
    if figs["license"]["name"] == "CC0":
        dcor["license_id"] = "CC0-1.0"
    else:
        raise ValueError(f"Unknown license: {figs['license']}")
    dcor["title"] = figs["title"]
    dcor["state"] = "draft"
    author_list = []
    for item in figs["authors"]:
        author_list.append(item["full_name"])
    dcor["authors"] = ", ".join(author_list)
    dcor["doi"] = figs["doi"]
    dcor["name"] = f"figshare-{figs['id']}-v{figs['version']}"
    dcor["organization"] = {"id": FIGSHARE_ORG}
    # markdownify and remove escapes "\_" with "_" (figshare-7771184-v2)
    dcor["notes"] = html2text(figs["description"]).replace(r"\_",
                                                           r"_")
    dcor["id"] = make_id([dcor["doi"], dcor["name"]])
    return dcor
