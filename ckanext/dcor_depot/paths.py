from dcor_shared import paths

#: CKAN storage path (contains resources, uploaded group, user or organization
#: images)
CKAN_STORAGE = paths.get_ckan_storage_path()

#: This is where DCOR keeps all relevant resource data
DEPOT_STORAGE = paths.get_dcor_depot_path()

#: CKAN resources location; This location will only contain symlinks to
#: the actual resources located in `USER_DEPOT`. However, ancillary
#: data such as preview images or condensed datasets are still stored here
#: (alongside the symlink).
CKAN_RESOURCES = CKAN_STORAGE / "resources"


#: Figshare data location on the backed-up block device
FIGSHARE_DEPOT = DEPOT_STORAGE / "figshare"

#: Internal archive data location used for Guck archive at mpl.mpg.de
#: (deprecated)
INTERNAL_DEPOT = DEPOT_STORAGE / "internal"

#: Resources itemized by user (contains the hostname)
USER_DEPOT = paths.get_dcor_users_depot_path()
