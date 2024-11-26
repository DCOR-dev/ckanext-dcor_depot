import logging
import warnings

from ckan import logic
from dcor_shared import (
    get_resource_path, rqjob_register, s3, s3cc, sha256sum, wait_for_resource)
from dcor_shared import RQJob  # noqa: F401

from .orgs import MANUAL_DEPOT_ORGS
from .paths import USER_DEPOT


log = logging.getLogger(__name__)


class NoSHA256Available(UserWarning):
    """Used for missing SHA256 sums"""
    pass


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


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
        if not s3cc.object_exists(rid, "resource"):
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


# TODO: Remove this method and make sure nothing depends on it.
def job_symlink_user_dataset(pkg, usr, resource):
    """Symlink resource data to human-readable depot"""
    warnings.warn("job_symlink_user_dataset should not be used",
                  DeprecationWarning)
    path = get_resource_path(resource["id"])
    if not path.exists():
        # nothing to do (skip, because resource is on S3 only)
        return False

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
                  / f"{pkg['name']}_{resource['id']}_{resource['name']}")

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
