import pathlib

from ckan import logic
from dcor_shared import get_ckan_config_option, s3, sha256sum

from .util import make_id


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def append_ckan_resource_to_active_dataset(dataset_id, res_dict):
    """Admin-only method to add a resource entry to a dataset

    This method is used in cases where you have to append a resource
    to a dataset that you have already uploaded or plan to upload to S3.

    You should provide a meaningful resource dictionary containing a
    resource ID (`"id"`) and the name of the resource (`"name"`).

    If the ID specified already exists in the dataset, then nothing
    is changed or updated.
    """
    for key in ["name", "id"]:
        if key not in res_dict:
            raise ValueError(f"You must provide '{key}' in `res_dict`")

    package_show = logic.get_action("package_show")
    ds_dict = package_show(context=admin_context(),
                           data_dict={"id": dataset_id})

    # Make sure the resource is in the CKAN database
    for res_other in ds_dict["resources"]:
        if res_dict["id"] == res_other["id"]:
            print(f"Resource {res_dict['name']} already in CKAN database")
            break
    else:
        print(f"Adding resource {res_dict['name']} to CKAN database")
        package_revise = logic.get_action("package_revise")
        package_revise(
            context=admin_context(),
            data_dict={"match__id": dataset_id,
                       "update__resources__extend": [res_dict]
                       }
        )


def append_resource(path, dataset_id, delete_source=False):
    """Upload a resource to S3 and append to an existing dataset"""
    package_show = logic.get_action("package_show")
    ds_dict = package_show(context=admin_context(),
                           data_dict={"id": dataset_id})

    sha256 = sha256sum(path)

    # Create a resource ID from the dataset ID and the resource hash
    rid = make_id([ds_dict["id"], path.name, sha256])

    # Upload the resource to S3
    bucket_name = get_ckan_config_option(
        "dcor_object_store.bucket_name").format(
        organization_id=ds_dict["organization"]["id"])
    object_name = f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}"
    s3_url = s3.upload_file(
        bucket_name=bucket_name,
        object_name=object_name,
        path=path,
        sha256=sha256,
        private=ds_dict["private"],
        override=False,
    )

    # Append the resource to the CKAN dataset entry
    append_ckan_resource_to_active_dataset(dataset_id=ds_dict["id"],
                                           res_dict={"id": rid,
                                                     "name": path.name,
                                                     "s3_available": True,
                                                     "s3_url": s3_url,
                                                     })

    # If we got here without any exceptions, then it is safe to
    # delete the input path.
    if delete_source:
        pathlib.Path(path).unlink()
