from unittest import mock
import pathlib

import pytest
import requests

import ckan.tests.factories as factories
import ckan.model
import ckan.common
import ckan.logic

from dcor_shared import get_ckan_config_option, get_resource_path, s3

from dcor_shared.testing import make_dataset_via_s3, synchronous_enqueue_job
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
        tmp_path):
    user = factories.User()
    user_obj = ckan.model.User.by_name(user["name"])
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
    ds_dict, res_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=True,
        resource_path=data_path / "calibration_beads_47.rtdc",
        private=True,
    )

    # make sure the dataset is private
    assert ds_dict["private"]

    rid = res_dict["id"]

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
