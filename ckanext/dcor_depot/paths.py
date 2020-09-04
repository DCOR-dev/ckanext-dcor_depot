import os
import socket

from ckan.common import config

hostname = socket.gethostname()

#: CKAN storage path (contains resources, uploaded group, user or organization
#: images)
CKAN_STORAGE = config.get('ckan.storage_path').rstrip("/")

#: CKAN resources location; This location will only contain symlinks to
#: the actual resources located in `USER_DEPOT`. However, ancillary
#: data such as preview images or condensed datasets are still stored here
#: (alongside the symlink).
CKAN_RESOURCES = CKAN_STORAGE + "/resources"

#: Figshare data location on the backed-up block device
FIGSHARE_DEPOT = "/data/depots/figshare"

#: Internal archive data location
INTERNAL_DEPOT = "/data/depots/internal"

#: Resources itemized by user (contains the hostname)
USER_DEPOT = "/data/depots/users-{}/".format(hostname)


def get_resource_path(rid, create_dirs=False):
    pdir = "{}/{}/{}".format(CKAN_RESOURCES, rid[:3], rid[3:6])
    path = "{}/{}".format(pdir, rid[6:])
    if create_dirs:
        try:
            os.makedirs(pdir)
        except OSError:
            pass
    os.chown(pdir,
             os.stat(CKAN_RESOURCES).st_uid,
             os.stat(CKAN_RESOURCES).st_gid)
    return path
