import os
import socket

hostname = socket.gethostname()

#: CKAN resources location (contains the hostname, starts with
#: ``ckan.storage_path`` from the CKAN configuration file)
CKAN_RESOURCES = "/data/ckan-{}/resources".format(hostname)

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
