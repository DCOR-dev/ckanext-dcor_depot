from unittest import mock

import pytest

from ckan.cli.cli import ckan as ckan_cli
from ckan.tests import helpers

from dcor_shared import s3cc
from dcor_shared.testing import make_dataset_via_s3, synchronous_enqueue_job

from ckanext.dcor_depot import app_res


def test_append_ckan_resource_requires_name_and_id():
    with pytest.raises(ValueError, match="You must provide 'id'"):
        app_res.append_ckan_resource_to_active_dataset(
            dataset_id="does-not-matter", res_dict={"name": "a.txt"})


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_append_resource(enqueue_job_mock, cli, tmp_path):
    path1 = tmp_path / "first.txt"
    path1.write_text("first resource")
    ds_dict, _ = make_dataset_via_s3(resource_path=path1, activate=True)

    path2 = tmp_path / "second.txt"
    path2.write_text("second resource")
    result = cli.invoke(ckan_cli, ["append-resource", str(path2),
                                   ds_dict["id"], "--delete-source"])
    assert result.exit_code == 0, result.output
    assert "Adding resource second.txt" in result.output
    assert not path2.exists()

    ds_dict = helpers.call_action("package_show", id=ds_dict["id"])
    assert len(ds_dict["resources"]) == 2
    res_dict = ds_dict["resources"][1]
    assert res_dict["name"] == "second.txt"
    assert res_dict["s3_available"]
    assert s3cc.artifact_exists(res_dict["id"], artifact="resource")

    # Appending the same file again does not add a resource
    path2.write_text("second resource")
    result = cli.invoke(ckan_cli, ["append-resource", str(path2),
                                   ds_dict["id"]])
    assert result.exit_code == 0, result.output
    assert "already in CKAN database" in result.output
    assert path2.exists()
    ds_dict = helpers.call_action("package_show", id=ds_dict["id"])
    assert len(ds_dict["resources"]) == 2
