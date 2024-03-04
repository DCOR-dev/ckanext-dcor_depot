from unittest import mock
import pathlib

import pytest

from ckan.cli.cli import ckan as ckan_cli
import ckan.tests.factories as factories
from ckan.tests import helpers
import ckan.model
import ckan.common
import ckanext.dcor_schemas.plugin
import ckanext.dcor_depot.jobs

import dcor_shared
import requests

from dcor_shared.testing import make_dataset, synchronous_enqueue_job
from dcor_shared.testing import create_with_upload_no_temp  # noqa: F401


data_path = pathlib.Path(__file__).parent / "data"


# Deactivate the dcor_depot plugin, so that the automatic upload to S3
# is not performed.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
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
    dataset = make_dataset(create_context,
                           owner_org,
                           activate=False)

    content = (data_path / "calibration_beads_47.rtdc").read_bytes()
    res_dict = create_with_upload_no_temp(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )

    dcor_shared.wait_for_resource(res_dict["id"])

    # Make sure the resource is not on S3 already
    res_dict = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" not in res_dict

    # Upload the resource initially
    result = cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store"])
    assert "Done!" in result.output
    assert f"Migrating dataset {dataset['id']}" in result.output
    assert f"Uploaded resource {res_dict['id'][:3]}" in result.output

    # Make sure the upload worked
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


# Deactivate the dcor_depot plugin, so that the automatic upload to S3
# is not performed.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_migrate_to_object_store_with_verify_existence(
        enqueue_job_mock,
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
    dataset = make_dataset(create_context,
                           owner_org,
                           activate=False)

    content = (data_path / "calibration_beads_47.rtdc").read_bytes()
    res_dict = create_with_upload_no_temp(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )

    dcor_shared.wait_for_resource(res_dict["id"])

    # Make sure the resource is not on S3 already
    res_dict = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" not in res_dict

    result = cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store"])

    assert "Done!" in result.output
    assert f"Migrating dataset {dataset['id']}" in result.output
    assert f"Uploaded resource {res_dict['id'][:3]}" in result.output

    resource = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" in resource
    assert "s3_url" in resource

    # Delete the resource from the object store
    s3_client, _, _ = dcor_shared.s3.get_s3()
    _, _stem = resource["s3_url"].split("//")
    serv, bucket, key = _stem.split("/", 2)
    s3_client.delete_object(Bucket=bucket, Key=key)

    # Make sure the object is not there anymore
    response = requests.get(resource["s3_url"])
    assert not response.ok
    assert response.status_code in [403, 404]

    # Attempt upload again (without verification)
    cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store"])
    response = requests.get(resource["s3_url"])
    assert not response.ok
    assert response.status_code in [403, 404]

    # Upload, this time with verification
    cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store",
                          "--verify-existence"])

    # Download the file and check the SHA256sum
    response = requests.get(resource["s3_url"])
    assert response.ok, "the resource is public, download should work"
    assert response.status_code == 200, "download public resource"
    dl_path = tmp_path / "calbeads.rtdc"
    with dl_path.open("wb") as fd:
        fd.write(response.content)
    assert dcor_shared.sha256sum(dl_path) == resource["sha256"]


# Deactivate the dcor_depot plugin, so that the automatic upload to S3
# is not performed.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_migrate_to_object_store_with_verify_checksum(
        enqueue_job_mock,
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
    dataset = make_dataset(create_context,
                           owner_org,
                           activate=False)

    content = (data_path / "calibration_beads_47.rtdc").read_bytes()
    res_dict = create_with_upload_no_temp(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )

    dcor_shared.wait_for_resource(res_dict["id"])

    # Make sure the resource is not on S3 already
    res_dict = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" not in res_dict

    # First call to CLI will cover the case when the resource does not exist
    result = cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store",
                                   "--verify-checksum"])
    assert "Done!" in result.output
    assert f"Migrating dataset {dataset['id']}" in result.output
    assert f"Verified resource {res_dict['id'][:3]}" in result.output
    resource = helpers.call_action("resource_show", id=res_dict["id"])
    assert "s3_available" in resource
    assert "s3_url" in resource

    # Run again. This time, the resource is only checked, not uploaded
    cli.invoke(ckan_cli, ["dcor-migrate-resources-to-object-store",
                          "--verify-checksum"])
    assert "Done!" in result.output
    assert f"Migrating dataset {dataset['id']}" in result.output
    assert f"Verified resource {res_dict['id'][:3]}" in result.output
