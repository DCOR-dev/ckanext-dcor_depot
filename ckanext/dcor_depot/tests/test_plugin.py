from unittest import mock
import pathlib

import pytest
import requests

import ckan.tests.factories as factories
import ckan.model
import ckan.common
import ckan.logic

import ckanext.dcor_schemas.plugin

from dcor_shared import get_ckan_config_option, get_resource_path, s3

from dcor_shared.testing import make_dataset, synchronous_enqueue_job
from dcor_shared.testing import create_with_upload_no_temp  # noqa: F401


data_path = pathlib.Path(__file__).parent / "data"


# dcor_depot must come first, because jobs are run in sequence and the
# symlink_user_dataset jobs must be executed first so that dcor_schemas
# does not complain about resources not available in wait_for_resource.
@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
# We have to use synchronous_enqueue_job, because the background workers
# are running as www-data and cannot move files across the file system.
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_after_dataset_update_make_private_public_on_s3(
        enqueue_job_mock,
        create_with_upload_no_temp,  # noqa: F811
        monkeypatch,
        tmp_path):
    monkeypatch.setattr(
        ckanext.dcor_schemas.plugin,
        'DISABLE_AFTER_DATASET_CREATE_FOR_CONCURRENT_JOB_TESTS',
        True)
    pass

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
    # Create a private dataset
    ds_dict, res_dict = make_dataset(
        create_context, owner_org,
        activate=True,
        create_with_upload=create_with_upload_no_temp,
        resource_path=data_path / "calibration_beads_47.rtdc",
        private=True,
    )

    # make sure the dataset is private
    assert ds_dict["private"]

    # upload the resource to S3
    rid = res_dict["id"]
    bucket_name = get_ckan_config_option(
        "dcor_object_store.bucket_name").format(
        organization_id=ds_dict["organization"]["id"])
    # Upload the resource to S3
    s3_url = s3.upload_file(
        bucket_name=bucket_name,
        object_name=f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}",
        path=str(get_resource_path(rid)),
        sha256=res_dict.get("sha256"),
        private=ds_dict["private"])
    # Update the resource dictionary
    ckan.logic.get_action("resource_patch")(
        context=create_context,
        data_dict={"id": rid,
                   "s3_available": True,
                   "s3_url": s3_url})

    # make sure this worked
    res_dict = ckan.logic.get_action("resource_show")(
        context=create_context,
        data_dict={"id": rid}
    )
    assert res_dict["s3_available"]

    # attempt to download the resource, which should fail, since it is private
    response = requests.get(res_dict["s3_url"])
    assert not response.ok
    assert response.status_code == 403

    # make the dataset public
    ckan.logic.get_action("package_patch")(
        context=create_context,
        data_dict={"id": ds_dict["id"],
                   "private": False}
    )

    # attempt to download - this time it should work
    response = requests.get(res_dict["s3_url"])
    assert response.ok
    assert response.status_code == 200
