from unittest import mock

import pytest

from ckan.cli.cli import ckan as ckan_cli

from dcor_shared.testing import make_dataset_via_s3, synchronous_enqueue_job


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_list_all_resources(enqueue_job_mock, cli, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("test resource")
    _, res_dict = make_dataset_via_s3(resource_path=path, activate=True)
    result = cli.invoke(ckan_cli, ["list-all-resources"])
    assert result.exit_code == 0, result.output
    assert res_dict["id"] in result.output


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_cli_list_s3_objects_for_dataset(enqueue_job_mock, cli, tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("test resource")
    ds_dict, res_dict = make_dataset_via_s3(resource_path=path,
                                            activate=True)
    rid = res_dict["id"]
    result = cli.invoke(ckan_cli, ["dcor-list-s3-objects-for-dataset",
                                   ds_dict["id"]])
    assert result.exit_code == 0, result.output
    assert f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}" in result.output
    # the dataset is public
    assert "public=true" in result.output


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_cli_prune_stale_multipart_uploads_dry_run(cli):
    result = cli.invoke(ckan_cli, ["dcor-prune-stale-multipart-uploads",
                                   "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Stale uploads found:" in result.output
    assert "Done!" in result.output
