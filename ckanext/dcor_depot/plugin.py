import os
import pathlib

import ckan.plugins as p
import ckan.plugins.toolkit as toolkit

from .cli import get_commands
from .orgs import MANUAL_DEPOT_ORGS
from .paths import USER_DEPOT

from dcor_shared import get_dataset_path


def symlink_user_dataset(path, pkg, usr, resource):
    """Symlink resource data to human-readable depot"""
    org = pkg["organization"]["name"]
    if org in MANUAL_DEPOT_ORGS:
        # nothing to do (skip, because already symlinked)
        return
    user = usr["name"]
    # depot path
    depot_path = pathlib.Path(USER_DEPOT) / user / \
        pkg["name"] / resource["name"]
    if not os.path.exists(str(depot_path.parent)):
        os.makedirs(str(depot_path.parent))
    # move file to depot and creat symlink back
    pathlib.Path(path).rename(depot_path)
    os.symlink(str(depot_path), path)


class DCORDepotPlugin(p.SingletonPlugin):
    p.implements(p.IClick)
    p.implements(p.IResourceController, inherit=True)

    # IClick
    def get_commands(self):
        return get_commands()

    # IResourceController
    def after_create(self, context, resource):
        # check organization
        pkg_id = resource["package_id"]
        pkg = toolkit.get_action('package_show')(context, {'id': pkg_id})
        # user name
        usr_id = pkg["creator_user_id"]
        usr = toolkit.get_action('user_show')(context, {'id': usr_id})
        # resource path
        path = get_dataset_path(context, resource)
        toolkit.enqueue_job(symlink_user_dataset, [path, pkg, usr, resource])
