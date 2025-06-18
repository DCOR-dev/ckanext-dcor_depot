ckanext-dcor_depot
==================

|PyPI Version| |Build Status| |Coverage Status|

This plugin manages how data are stored in DCOR. There are two types of
files in DCOR:

1. Resources uploaded by users, imported from figshare, or
   imported from a data archive
2. Ancillary files that are generated upon resource creation, such as
   condensed DC data, preview images (see
   `ckanext-dc_view <https://github.com/DCOR-dev/ckanext-dc_view>`_).

This plugin implements:

- A background job that uploads resources to S3 in `after_resource_create`
  if the resources were previously uploaded via the legacy upload route.
  This functionality is interesting for legacy setups that are not using
  S3 object storage by default.
- Import datasets from figshare. Existing datasets on figshare are
  parsed, datasets are created and resources uploaded to S3 object storage.
  When running the following command, the "figshare-import" organization
  is created and the datasets listed in ``figshare_dois.txt`` are added to CKAN:

  ::

     ckan dcor-import-figshare --limit 2


- CLI for running all background jobs (migration to S3):

  ::

     ckan run-jobs-dcor-depot


- CLI for appending a resource to a dataset

  ::

     ckan append-resource /path/to/file dataset_id --delete-source



- CLI for migrating data from block storage to an S3-compatible object storage
  service. For this, the following configuration keys must be specified in
  the ``ckan.ini`` file::

    dcor_object_store.access_key_id = ACCESS_KEY_ID
    dcor_object_store.secret_access_key = SECRET_ACCESS_KEY
    dcor_object_store.endpoint_url = S3_ENDPOINT_URL
    dcor_object_store.ssl_verify = true
    # The bucket name is by default defined by the circle ID. Resources
    # are stored in the "RES/OUR/CEID-SCHEME" in that bucket.
    dcor_object_store.bucket_name = circle-{organization_id}

  Usage::

    ckan dcor-migrate-resources-to-object-store --modified-days 2 --delete-after-migration --verify-checksum

- CLI for listing all S3 objects for a dataset::

    ckan dcor-list-s3-objects-for-dataset c7a98a04-4e0a-98a7-fb0b-eca379d1f219

- CLI for listing all resources::

    ckan list-all-resources

- CLI for pruning stale multipart uploads::

    ckan dcor-prune-stale-multipart-uploads --initiated-before-days 5 --dry-run


Installation
------------

::

    pip install ckanext-dcor_depot


Add this extension to the plugins and default_views in ckan.ini:

::

    ckan.plugins = [...] dcor_depot
    ckan.storage_path=/data/ckan-HOSTNAME
    ckanext.dcor_depot.users_depot_name=users-HOSTNAME

This plugin stores resources to `/data`:

::

    mkdir -p /data/depots/users-$(hostname)
    chown -R www-data /data/depots/users-$(hostname)


Testing
-------
If CKAN/DCOR is installed and setup for testing, this extension can
be tested with pytest:

::

    pytest ckanext

Testing is implemented via GitHub Actions. You may also set up a local
docker container with CKAN and MinIO. Take a look at the GitHub Actions
workflow for more information.


.. |PyPI Version| image:: https://img.shields.io/pypi/v/ckanext.dcor_depot.svg
   :target: https://pypi.python.org/pypi/ckanext.dcor_depot
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/DCOR-dev/ckanext-dcor_depot/check.yml
   :target: https://github.com/DCOR-dev/ckanext-dcor_depot/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/DCOR-dev/ckanext-dcor_depot
   :target: https://codecov.io/gh/DCOR-dev/ckanext-dcor_depot
