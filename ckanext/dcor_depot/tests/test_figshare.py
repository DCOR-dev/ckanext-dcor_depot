"""Tests for the figshare import (figshare servers are never contacted)"""
import hashlib
import io
import json
from unittest import mock

import pytest

from ckan.cli.cli import ckan as ckan_cli
from ckan.tests import helpers

from dcor_shared.testing import synchronous_enqueue_job

from ckanext.dcor_depot import figshare


FILE_DATA = b"This is the content of the README file."


def make_figshare_dict(license_name="CC0"):
    """Minimal metadata as returned by the figshare API"""
    return {
        "id": 7771184,
        "version": 2,
        "doi": "10.6084/m9.figshare.7771184.v2",
        "title": "Test figshare dataset",
        "description": "<p>Description with an_underscore</p>",
        "license": {"name": license_name},
        "authors": [{"full_name": "Peter Pan"},
                    {"full_name": "Wendy Darling"}],
        "references": ["https://example.com/paper",
                       "10.1000/xyz123"],
        "files": [
            {"is_link_only": False,
             "name": "README.txt",
             "supplied_md5": hashlib.md5(FILE_DATA).hexdigest(),
             "download_url": "https://example.com/download/README.txt",
             },
            {"is_link_only": True,
             "name": "link_only.rtdc",
             },
        ],
    }


def test_map_figshare_to_dcor():
    dcor = figshare.map_figshare_to_dcor(make_figshare_dict())
    assert dcor["name"] == "figshare-7771184-v2"
    assert dcor["owner_org"] == figshare.FIGSHARE_ORG
    assert dcor["license_id"] == "CC0-1.0"
    assert dcor["authors"] == "Peter Pan, Wendy Darling"
    assert dcor["references"] == \
        "https://example.com/paper, doi:10.1000/xyz123"
    assert dcor["state"] == "draft"
    assert "an_underscore" in dcor["notes"]
    # identifiers are reproducible
    assert dcor["id"] == figshare.map_figshare_to_dcor(
        make_figshare_dict())["id"]


def test_map_figshare_to_dcor_unknown_license():
    with pytest.raises(ValueError, match="Unknown license"):
        figshare.map_figshare_to_dcor(make_figshare_dict("CC-BY"))


def mock_urlopen(request):
    """Return the figshare API response for a request"""
    resp = io.BytesIO(json.dumps(make_figshare_dict()).encode("utf-8"))
    resp.status = 200
    return resp


def mock_requests_get(url, stream=False):
    """Return the file download response for a request"""
    resp = mock.MagicMock()
    resp.__enter__.return_value = resp
    resp.iter_content.return_value = [FILE_DATA]
    return resp


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
@mock.patch("ckanext.dcor_depot.figshare.requests.get",
            side_effect=mock_requests_get)
@mock.patch("ckanext.dcor_depot.figshare.urllib.request.urlopen",
            side_effect=mock_urlopen)
def test_import_figshare(urlopen_mock, get_mock, enqueue_job_mock, cli):
    result = cli.invoke(ckan_cli, ["dcor-import-figshare", "--limit", "1"])
    assert result.exit_code == 0, result.output
    assert urlopen_mock.call_count == 1
    assert get_mock.call_count == 1

    ds_dict = helpers.call_action("package_show", id="figshare-7771184-v2")
    assert ds_dict["state"] == "active"
    assert ds_dict["organization"]["name"] == figshare.FIGSHARE_ORG
    # the link-only file is not imported
    assert len(ds_dict["resources"]) == 1
    assert ds_dict["resources"][0]["name"] == "README.txt"
    assert ds_dict["resources"][0]["s3_available"]

    # A second import does not download anything
    result = cli.invoke(ckan_cli, ["dcor-import-figshare", "--limit", "1"])
    assert result.exit_code == 0, result.output
    assert "already on S3" in result.output
    assert get_mock.call_count == 1
