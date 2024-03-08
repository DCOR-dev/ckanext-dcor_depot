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

- Data storage management. All resources uploaded by a user are moved
  to ``/data/users-HOSTNAME/USERNAME-ORGNAME/PK/ID/PKGNAME_RESID_RESNAME``
  and symlinks are created in ``/data/ckan-HOSTNAME/resources/RES/OUR/CEID``
  via a background job.
  CKAN itself will not notice this. The idea is to have a filesystem overview
  about the datasets of each user.
- A backround job that uploads resources to S3 in `after_resource_create`
  if the resources were uploaded via the legacy upload route.
- A background job that backs up resources from S3 to local block storage
  if the resources were uploaded via the S3 upload route.
- Import datasets from figshare. Existing datasets from figshare are
  downloaded to the ``/data/depots/figshare`` directory and, upon resource
  creation, symlinked there from  ``/data/ckan-HOSTNAME/resources/RES/OUR/CEID``
  (Note that this is an exemption of the data storage management described
  above). When running the following command, the "figshare-import" organization
  is created and the datasets listed in ``figshare_dois.txt`` are added to CKAN:

  ::

     ckan import-figshare


- CLI for symlinking datasets that have failed to symlink before:

  ::

     ckan run-jobs-dcor-depot


- CLI for appending a resource to a dataset

  ::

     ckan append-resource /path/to/file dataset_id --delete-source

Please make sure that the necessary file permissions are given in ``/data``.

In 2023, it was decided that the huge block storage of DCOR
should be replaced with an S3-compatible object store, because block storage
does not scale well. This partially deprecates some of the commands above
which might be removed or modified to support object storage directly.

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

    ckan dcor-migrate-resources-to-object-store


Installation
------------

::

    pip install ckanext-dcor_depot


Add this extension to the plugins and defaul_views in ckan.ini:

::

    ckan.plugins = [...] dcor_depot
    ckan.storage_path=/data/ckan-HOSTNAME
    ckanext.dcor_depot.depots_path=/data/depots
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

Testing can also be done via vagrant in a virtualmachine using the
`dcor-test <https://app.vagrantup.com/paulmueller/boxes/dcor-test/>` image.
Make sure that `vagrant` and `virtualbox` are installed and run the
following commands in the root of this repository:

::

    # Setup virtual machine using `Vagrantfile`
    vagrant up
    # Run the tests
    vagrant ssh -- sudo bash /testing/vagrant-run-tests.sh


.. |PyPI Version| image:: https://img.shields.io/pypi/v/ckanext.dcor_depot.svg
   :target: https://pypi.python.org/pypi/ckanext.dcor_depot
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/DCOR-dev/ckanext-dcor_depot/check.yml
   :target: https://github.com/DCOR-dev/ckanext-dcor_depot/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/DCOR-dev/ckanext-dcor_depot
   :target: https://codecov.io/gh/DCOR-dev/ckanext-dcor_depot
