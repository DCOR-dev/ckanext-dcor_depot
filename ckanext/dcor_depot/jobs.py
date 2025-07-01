import logging
import os
import pathlib
import warnings

from ckan import logic
from dcor_shared import (
    get_ckan_storage_path, rqjob_register, s3, s3cc, sha256sum,
    wait_for_resource,
)
from dcor_shared import RQJob  # noqa: F401


log = logging.getLogger(__name__)


class NoSHA256Available(UserWarning):
    """Used for missing SHA256 sums"""
    pass


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def get_resource_path(resource_id, create_dirs=False):
    """Return the expected local path for a resource identifier

    If `create_dirs` is True, create the parent directory tree.
    """
    warnings.warn("`get_resource_path` should not be used since DCOR moved "
                  "to storing data solely on S3",
                  DeprecationWarning)
    rid = resource_id
    resources_path = get_ckan_storage_path() / "resources"
    pdir = resources_path / rid[:3] / rid[3:6]
    path = pdir / rid[6:]
    if create_dirs:
        try:
            pdir.mkdir(parents=True, exist_ok=True)
            os.makedirs(pdir)
            os.chown(pdir,
                     os.stat(resources_path).st_uid,
                     os.stat(resources_path).st_gid)
        except OSError:
            pass
    return pathlib.Path(path)


def patch_resource_noauth(package_id, resource_id, data_dict):
    """Patch a resource using package_revise"""
    package_revise = logic.get_action("package_revise")
    revise_dict = {"match": {"id": package_id},
                   f"update__resources__{resource_id}": data_dict}
    package_revise(context=admin_context(), data_dict=revise_dict)


@rqjob_register(ckanext="dcor_depot",
                queue="dcor-normal",
                timeout=3600,
                )
def job_migrate_resource_to_s3(resource):
    """Migrate a resource to the S3 object store"""
    if not s3.is_available():
        log.info("S3 not available, not migrating resource")
        return False

    performed_upload = False
    rid = resource["id"]
    # Make sure the resource is available for processing
    wait_for_resource(rid)
    path = get_resource_path(rid)

    # Only attempt to upload if the file has been uploaded to block storage.
    if path.exists():
        sha256 = resource.get("sha256")
        if sha256 is None:
            warnings.warn(f"Resource {rid} has no SHA256 sum yet and I will "
                          f"compute it now. This should not happen unless you "
                          f"are running pytest with synchronous jobs!",
                          NoSHA256Available)
            sha256 = sha256sum(path)

        # Tell whether we have to perform an upload.
        if not s3cc.artifact_exists(rid, "resource"):
            performed_upload = True

        # Perform the upload (if necessary), returning the URL
        s3_url = s3cc.upload_artifact(
            resource_id=rid,
            path_artifact=path,
            artifact="resource",
            # avoid an empty SHA256 string being passed to the method
            sha256=sha256,
            override=False,
        )

        # Set the S3 URL in the resource metadata
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict={
                "s3_available": True,
                "s3_url": s3_url})

    return performed_upload
