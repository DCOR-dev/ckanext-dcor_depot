from io import BytesIO
import mock
import pathlib

import pytest

from ckan.cli.cli import ckan as ckan_cli
import ckan.tests.factories as factories
from ckan.tests import helpers
from ckan.tests.pytest_ckan.fixtures import FakeFileStorage
import ckan.model
import ckan.common
import ckanext.dcor_schemas.plugin

import dcor_shared
import requests

from .helper_methods import make_dataset


data_dir = pathlib.Path(__file__).parent / "data"


def synchronous_enqueue_job(job_func, args=None, kwargs=None, title=None,
                            queue=None, rq_kwargs=None):
    """
    Synchronous mock for ``ckan.plugins.toolkit.enqueue_job``.
    """
    if rq_kwargs is None:
        rq_kwargs = {}
    args = args or []
    kwargs = kwargs or {}
    job_func(*args, **kwargs)


@pytest.fixture
def create_with_upload_no_temp(clean_db, ckan_config, monkeypatch):
    """
    Create upload without tempdir
    """

    def factory(data, filename, context=None, **kwargs):
        if context is None:
            context = {}
        action = kwargs.pop("action", "resource_create")
        field = kwargs.pop("upload_field_name", "upload")
        test_file = BytesIO()
        if type(data) is not bytes:
            data = bytes(data, encoding="utf-8")
        test_file.write(data)
        test_file.seek(0)
        test_resource = FakeFileStorage(test_file, filename)

        params = {
            field: test_resource,
        }
        params.update(kwargs)
        return helpers.call_action(action, context, **params)
    return factory


# dcor_depot must come first, because jobs are run in sequence and the
# symlink_user_dataset jobs must be executed first so that dcor_schemas
# does not complain about resources not available in wait_for_resource.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_migrate_to_object_store(enqueue_job_mock,
                                     create_with_upload_no_temp,
                                     monkeypatch,
                                     cli,
                                     tmp_path):
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    user_obj = ckan.model.User.by_name(user["name"])
    monkeypatch.setattr(ckan.common,
                        'current_user',
                        user_obj)
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'auth_user_obj': user_obj,
                      'user': user['name'],
                      'api_version': 3}
    dataset = make_dataset(create_context, owner_org,
                           activate=False)

    content = (data_dir / "calibration_beads_47.rtdc").read_bytes()
    res_dict = create_with_upload_no_temp(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )

    res_path = dcor_shared.get_resource_path(res_dict["id"])
    dcor_shared.wait_for_resource(res_path)

    result = cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store"])

    assert "Done!" in result.output
    assert f"Migrating dataset {dataset['id']}" in result.output
    assert f"Uploaded resource {res_dict['name']}" in result.output

    resource = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" in resource
    assert "s3_url" in resource

    # Download the file and check the SHA256sum
    response = requests.get(resource["s3_url"])
    assert response.ok, "the resource is public, download should work"
    assert response.status_code == 200, "download public resource"
    dl_path = tmp_path / "calbeads.rtdc"
    with dl_path.open("wb") as fd:
        fd.write(response.content)
    assert dcor_shared.sha256sum(dl_path) == resource["sha256"]
