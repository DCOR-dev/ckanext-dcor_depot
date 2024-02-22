"""Testing background jobs

Due to the asynchronous nature of background jobs, code that uses them needs
to be handled specially when writing tests.

A common approach is to use the mock package to replace the
ckan.plugins.toolkit.enqueue_job function with a mock that executes jobs
synchronously instead of asynchronously
"""
import pathlib
from unittest import mock

import pytest
import requests

import ckan.lib
import ckan.tests.factories as factories
from ckan.tests import helpers

import ckanext.dcor_schemas.plugin
import dcor_shared

from dcor_shared.testing import make_dataset, synchronous_enqueue_job


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_migrate_to_s3_public_dataset(enqueue_job_mock, create_with_upload,
                                      monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    ds_dict, rs_dict = make_dataset(
        create_context,
        owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)
    # Check the resource
    resource = helpers.call_action("resource_show", id=rs_dict["id"])
    assert resource["s3_available"]
    s3_url = resource["s3_url"]
    response = requests.get(s3_url)
    assert response.ok, "the resource is public, download should work"
    assert response.status_code == 200, "download public resource"
    dl_path = tmpdir / "calbeads.rtdc"
    with dl_path.open("wb") as fd:
        fd.write(response.content)
    assert dcor_shared.sha256sum(dl_path) == dcor_shared.sha256sum(
        data_path / "calibration_beads_47.rtdc")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_migrate_to_s3_private_dataset(enqueue_job_mock, create_with_upload,
                                       monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    ds_dict, rs_dict = make_dataset(
        create_context,
        owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        private=True)
    # Check the resource
    resource = helpers.call_action("resource_show", id=rs_dict["id"])
    assert resource["s3_available"]
    s3_url = resource["s3_url"]
    response = requests.get(s3_url)
    assert not response.ok, "resource is private"
    assert response.status_code == 403, "resource is private"


# dcor_depot must come first, because jobs are run in sequence and the
# symlink_user_dataset jobs must be executed first so that dcor_schemas
# does not complain about resources not available in wait_for_resource.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_symlink_user_dataset(enqueue_job_mock, create_with_upload,
                              monkeypatch, ckan_config, tmpdir):
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader,
                        'get_storage_path',
                        lambda: str(tmpdir))
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)

    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    dataset = make_dataset(create_context,
                           owner_org,
                           activate=False)

    content = (data_path / "calibration_beads_47.rtdc").read_bytes()
    result = create_with_upload(
        content, 'test.rtdc',
        url="upload",
        package_id=dataset["id"],
        context=create_context,
    )

    resource = helpers.call_action("resource_show", id=result["id"])
    rpath = dcor_shared.get_resource_path(result["id"])
    assert rpath.exists()
    assert rpath.is_symlink()
    assert rpath.resolve().name == \
           f"{dataset['name']}_{resource['id']}_{resource['name']}"
    assert rpath.resolve().parent.name == dataset["id"][2:4]
    assert rpath.resolve().parent.parent.name == dataset["id"][:2]
