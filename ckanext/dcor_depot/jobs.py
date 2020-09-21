import pathlib

from dcor_shared import get_resource_path

from .orgs import MANUAL_DEPOT_ORGS
from .paths import USER_DEPOT


def symlink_user_dataset(pkg, usr, resource):
    """Symlink resource data to human-readable depot"""
    path = get_resource_path(resource["id"])
    org = pkg["organization"]["name"]
    if org in MANUAL_DEPOT_ORGS:
        # nothing to do (skip, because already symlinked)
        return
    user = usr["name"]
    # depot path
    depot_path = (pathlib.Path(USER_DEPOT)
                  / (user + "-" + org)
                  / pkg["id"][:2]
                  / pkg["id"][2:4]
                  / "{}_{}_{}".format(pkg["name"],
                                      resource["id"],
                                      resource["name"]))
    if not depot_path.parent.exists():
        depot_path.parent.mkdir(exist_ok=True, parents=True)
    # move file to depot and create symlink back
    path = pathlib.Path(path)
    path.rename(depot_path)
    path.symlink_to(depot_path)
