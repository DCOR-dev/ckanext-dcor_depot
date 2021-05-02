import pathlib
import shutil
import tempfile

from ckanext.dcor_depot.depotize import depotize
from ckanext.dcor_depot.internal import internal, make_dataset_dict, \
    internal_upgrade
import ckan
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared import get_resource_path, wait_for_resource

import h5py
import pytest


data_path = pathlib.Path(__file__).parent / "data"

#: data from depotize_archive_20210123.tar.gz
depotized_data = [
    "/data/depots/internal/202X/2021-01/01/2021-01-01_1515_01ca24*",
    "/data/depots/internal/202X/2021-01/01/2021-01-01_2112_010767*",
    "/data/depots/internal/202X/2021-01/23/2021-01-23_1515_eb5b0e*",
]


def remove_depotized():
    for stem in depotized_data:
        stemp = pathlib.Path(stem)
        for pp in stemp.parent.glob(stemp.name):
            pp.unlink()


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    remove_depotized()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    remove_depotized()


@pytest.mark.ckan_config('ckan.plugins', 'dcor_depot dcor_schemas dc_view')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_internal_upgrade(monkeypatch, ckan_config, tmpdir):
    """depotize and import"""
    monkeypatch.setitem(ckan_config, 'ckan.storage_path', str(tmpdir))
    monkeypatch.setattr(ckan.lib.uploader, '_storage_path', str(tmpdir))
    # depotize
    name = "depotize_archive_20210123.tar.gz"
    path = pathlib.Path(tempfile.mkdtemp()) / name
    shutil.copy2(data_path / name, path)
    depotize(path)
    # import
    internal(start_date="2020-01-01", end_date="2021-01-23")
    # create another version for one of the datasets
    stem = depotized_data[1][:-1]
    path_v1 = pathlib.Path(stem + "_v1.rtdc")
    path_v2 = pathlib.Path(stem + "_v2.rtdc")
    shutil.copy2(path_v1, path_v2)
    with h5py.File(path_v2, "r+") as h5:
        h5.attrs["experiment:sample"] = "Thor!"
    # now run the upgrade command
    internal_upgrade(start_date="2020-01-01", end_date="2021-01-23")
    # check whether the v2 datasets exists
    admin = factories.Sysadmin()
    context = {'ignore_auth': True, 'user': admin['name']}
    # determine all dataset IDs
    computed_id = make_dataset_dict(path_v1)["id"]
    data_dict = helpers.call_action("package_show", context,
                                    id=computed_id)
    res_list = data_dict["resources"]
    assert data_dict["state"] == "active"
    namestem = pathlib.Path(stem).name
    assert res_list[0]["name"] == namestem + "_v2.rtdc"
    assert res_list[1]["name"] == namestem + "_v1.rtdc"
    assert res_list[2]["name"] == namestem + "_ad1_m002_bg.png"
    assert res_list[3]["name"] == namestem + "_ad2_m002_softwaresettings.ini"

    p1 = get_resource_path(res_list[1]["id"])
    wait_for_resource(p1)
    with h5py.File(p1, "r") as h5:
        assert h5.attrs["experiment:sample"] == "calibration_beads"

    p2 = get_resource_path(res_list[0]["id"])
    wait_for_resource(p2)
    with h5py.File(p2, "r") as h5:
        assert h5.attrs["experiment:sample"] == "Thor!"
