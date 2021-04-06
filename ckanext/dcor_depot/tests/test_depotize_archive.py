import pathlib
import shutil
import tempfile

from ckanext.dcor_depot.depotize import depotize
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


def test_depotize_tar_archive():
    """Test whether depotize functionality works"""
    name = "depotize_archive_20210123.tar.gz"
    path = pathlib.Path(tempfile.mkdtemp()) / name
    shutil.copy2(data_path / name, path)
    depotize(path)
    for stem in depotized_data:
        stemp = pathlib.Path(stem)
        files = list(stemp.parent.glob(stemp.name))
        # Make sure that the files were stored in the correct directory
        # with the correct stem.
        assert len(files) >= 3, stem


if __name__ == "__main__":
    # Run all tests
    loc = locals()
    for key in list(loc.keys()):
        if key.startswith("test_") and hasattr(loc[key], "__call__"):
            loc[key]()
