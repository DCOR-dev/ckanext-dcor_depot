from dcor_shared import get_resource_path

from .orgs import MANUAL_DEPOT_ORGS
from .paths import USER_DEPOT


def symlink_user_dataset(pkg, usr, resource):
    """Symlink resource data to human-readable depot"""
    path = get_resource_path(resource["id"])
    org = pkg["organization"]["name"]
    if org in MANUAL_DEPOT_ORGS or path.is_symlink():
        # nothing to do (skip, because already symlinked)
        return False
    user = usr["name"]
    # depot path
    depot_path = (USER_DEPOT
                  / (user + "-" + org)
                  / pkg["id"][:2]
                  / pkg["id"][2:4]
                  / "{}_{}_{}".format(pkg["name"],
                                      resource["id"],
                                      resource["name"]))
    if not depot_path.parent.exists():
        depot_path.parent.mkdir(exist_ok=True, parents=True)

    symlinked = True

    # move file to depot and create symlink back
    try:
        path.rename(depot_path)
    except FileNotFoundError:
        # somebody else was faster (avoid race conditions)
        if not depot_path.exists():
            raise
        else:
            symlinked = False

    try:
        path.symlink_to(depot_path)
    except FileNotFoundError:
        # somebody else was faster (avoid race conditions)
        if not path.is_symlink():
            raise
        else:
            symlinked = False

    return symlinked
