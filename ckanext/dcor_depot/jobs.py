import os
import pathlib
import warnings

from dcor_shared import get_ckan_storage_path


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
