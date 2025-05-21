from dcor_shared import paths

#: CKAN storage path (contains resources, uploaded group, user or organization
#: images)
CKAN_STORAGE = paths.get_ckan_storage_path()

#: This is where DCOR keeps all relevant resource data
DEPOT_STORAGE = paths.get_dcor_depot_path()

#: CKAN resources location; Nothing should actually be stored here,
#: since we are uploading all resources directly to S3.
CKAN_RESOURCES = CKAN_STORAGE / "resources"

#: Figshare data location on the backed-up block device
FIGSHARE_DEPOT = DEPOT_STORAGE / "figshare"

#: Internal archive data location used for Guck archive at mpl.mpg.de
#: (deprecated)
INTERNAL_DEPOT = DEPOT_STORAGE / "internal"
