ckanext-dcor_depot
==================

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
  and symlinks are created in ``/data/ckan-HOSTNAME/resources/RES/OUR/CEID``.
  CKAN itself will not notice this. The idea is to have a filesystem overview
  about the datasets of each user.
- Import datasets from figshare. Existing datasets from figshare are
  downloaded to the ``/data/depots/figshare`` directory and, upon resource
  creation, symlinked there from  ``/data/ckan-HOSTNAME/resources/RES/OUR/CEID``
  (Note that this is an exemption of the data storage management described
  above). When running the following command, the "figshare-import" organization
  is created and the datasets listed in ``figshare_dois.txt`` are added to CKAN:

  ::

     ckan -c /etc/ckan/default/ckan.ini import-figshare

Please make sure that the necessary file permissions are given in ``/data``. 


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
