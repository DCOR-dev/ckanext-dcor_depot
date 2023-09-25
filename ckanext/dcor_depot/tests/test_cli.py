import mock
import pathlib

import pytest

from ckan.cli.cli import ckan as ckan_cli
import ckan.tests.factories as factories
from ckan.tests import helpers
import ckan.model
import ckan.common
import ckanext.dcor_schemas.plugin

import dcor_shared
import requests

from .helper_methods import make_dataset, synchronous_enqueue_job
from .helper_methods import create_with_upload_no_temp  # noqa: F401


data_dir = pathlib.Path(__file__).parent / "data"


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
                                     create_with_upload_no_temp,  # noqa: F811
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
