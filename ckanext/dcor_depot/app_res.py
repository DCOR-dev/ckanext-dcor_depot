import pathlib
import shutil

from ckan import logic

from .depot import make_id, sha_256
from .internal import import_resource
from . import paths


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def append_resource(path, dataset_id, copy=True):
    """Append a resource to a dataset, copying it to the correct path"""

    package_show = logic.get_action("package_show")
    dataset_dict = package_show(context=admin_context(),
                                data_dict={"id": dataset_id})

    path_hash = sha_256(path)

    # Create a resource ID from the dataset ID and the resource hash
    resource_id = make_id([dataset_dict["id"],
                           path.name,
                           path_hash,
                           ])

    # Determine the resource depot path (matches ID in `import_resource`)
    resource_depot_path = get_depot_path_for_resource(
        res_id=resource_id,
        res_name=path.name,
        pkg_dict=dataset_dict
        )

    resource_show = logic.get_action("resource_show")
    try:
        resource_show(context=admin_context(), data_dict={"id": resource_id})
    except logic.NotFound:
        if copy:
            shutil.copy2(path, resource_depot_path)
        else:
            pathlib.Path(path).rename(resource_depot_path)
        # In contrast to the other importing methods (figshare, internal),
        # we don't automatically add a condensed version of the dataset.
        # I think it does not really matter where you do it, so it is
        # probably fine to let the background workers do it.
        # import the resource
        import_resource(dataset_dict,
                        resource_depot_path=resource_depot_path,
                        sha256_sum=path_hash,
                        resource_name=pathlib.Path(path).name,
                        )
    else:
        print(f"Skipping resource {resource_id} (exists)", flush=True)


def get_depot_path_for_resource(res_id, res_name, pkg_dict):
    user_show = logic.get_action("user_show")
    usr_dict = user_show(context=admin_context(),
                         data_dict={"id": pkg_dict["creator_user_id"]})
    usr_name = usr_dict["name"]
    pkg_id = pkg_dict["id"]
    pkg_name = pkg_dict["name"]
    org = pkg_dict["organization"]["name"]
    # depot path
    resource_depot_path = (paths.USER_DEPOT
                           / (usr_name + "-" + org)
                           / pkg_id[:2]
                           / pkg_id[2:4]
                           / "{}_{}_{}".format(pkg_name,
                                               res_id,
                                               res_name))
    return resource_depot_path
