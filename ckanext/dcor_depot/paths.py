import socket
import warnings

from ckan.common import config

#: CKAN storage path (contains resources, uploaded group, user or organization
#: images)
CKAN_STORAGE = config.get('ckan.storage_path', "").rstrip("/")

#: This is where DCOR keeps all relevant resource data
DEPOT_STORAGE = config.get('ckanext.dcor_depot.depots_path', "").rstrip("/")
if not DEPOT_STORAGE:
    DEPOT_STORAGE = "/data/depots"
    warnings.warn("Please set 'ckanext.dcor_depot.depots_path' in ckan.ini!")

#: Name of the USER_DEPOT
USER_DEPOT_NAME = config.get('ckanext.dcor_depot.users_depot_name',
                             "").rstrip("/")
if not USER_DEPOT_NAME:
    USER_DEPOT_NAME = "users-{}".format(socket.gethostname())
    warnings.warn(
        "Please set 'ckanext.dcor_depot.users_depot_name' in ckan.ini!")

#: CKAN resources location; This location will only contain symlinks to
#: the actual resources located in `USER_DEPOT`. However, ancillary
#: data such as preview images or condensed datasets are still stored here
#: (alongside the symlink).
CKAN_RESOURCES = CKAN_STORAGE + "/resources"


#: Figshare data location on the backed-up block device
FIGSHARE_DEPOT = DEPOT_STORAGE + "/figshare"

#: Internal archive data location
INTERNAL_DEPOT = DEPOT_STORAGE + "/internal"

#: Resources itemized by user (contains the hostname)
USER_DEPOT = DEPOT_STORAGE + "/" + USER_DEPOT_NAME
