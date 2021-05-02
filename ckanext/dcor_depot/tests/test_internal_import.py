import pathlib
import shutil
import tempfile

from ckanext.dcor_depot.depotize import depotize
from ckanext.dcor_depot.internal import internal, make_dataset_dict

import ckan.tests.factories as factories
import ckan.tests.helpers as helpers


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
def test_internal_import():
    """depotize and import"""
    # depotize
    name = "depotize_archive_20210123.tar.gz"
    path = pathlib.Path(tempfile.mkdtemp()) / name
    shutil.copy2(data_path / name, path)
    depotize(path)
    # import
    internal(start_date="2020-01-01", end_date="2021-01-23")
    # check whether the datasets exists
    admin = factories.Sysadmin()
    context = {'ignore_auth': True, 'user': admin['name']}
    # determine all dataset IDs
    for stem in depotized_data:
        rpath = pathlib.Path(stem[:-1] + "_v1.rtdc")
        computed_id = make_dataset_dict(rpath)["id"]
        dataset_name = stem.split("/")[-1].strip("*")
        data_dict = helpers.call_action("package_show", context,
                                        id=computed_id)
        assert data_dict["name"] == dataset_name
        assert data_dict["id"] == computed_id
        assert data_dict["state"] == "active"
