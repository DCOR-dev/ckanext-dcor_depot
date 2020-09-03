import pathlib

from .orgs import MANUAL_DEPOT_ORGS
from .paths import USER_DEPOT


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
    if not depot_path.parent.exists():
        depot_path.parent.mkdir(exist_ok=True, parents=True)
    # move file to depot and creat symlink back
    path = pathlib.Path(path)
    path.rename(depot_path)
    path.symlink_to(depot_path)
