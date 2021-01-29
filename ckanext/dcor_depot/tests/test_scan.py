import pathlib
import tempfile

from ckanext.dcor_depot.depotize import scan


def test_find_associates():
    tdir = pathlib.Path(tempfile.mkdtemp(prefix="test_find_associates_"))
    path = tdir / "M0_0.008000ul_s.tdms"
    associates = ["M0_0.008000ul_s.tdms_index",
                  "M0_camera.ini",
                  "M0_extraDebug.txt",
                  "M0_para.ini",
                  ]
    for name in associates + [path]:
        (tdir / name).touch()

    ass = scan.find_associates(path, "scan_associate_tdms.json")
    for name in associates:
        assert (tdir / name) in ass


def test_scan_tdms():
    tdir = pathlib.Path(tempfile.mkdtemp(prefix="test_find_associates_"))
    wdir = tdir / "data"
    wdir.mkdir()
    path = wdir / "M0_0.008000ul_s.tdms"
    associates = ["M0_0.008000ul_s.tdms_index",
                  "M0_camera.ini",
                  "M0_extraDebug.txt",
                  "M0_para.ini",
                  "M0_SoftwareSettings.ini",
                  "M0_bg.png",
                  ]
    for name in associates + [path]:
        (wdir / name).touch()

    res = scan.scan(wdir)
    assert res[0]["datasets"] == 1
    assert res[0]["datasets with ancillaries"] == 1
    assert res[0]["datasets excluded"] == 0
    assert res[0]["files unknown"] == 0

    assert len(res[1]["datasets"]) == 1
    assert len(res[1]["datasets with ancillaries"]) == 1
    assert len(res[1]["datasets with ancillaries"][path]) == 1
    assert res[1]["datasets with ancillaries"][path][0].name == \
           "M0_bg.png"
    assert len(res[1]["datasets excluded"]) == 0
    assert len(res[1]["files unknown"]) == 0
    assert len(res[1]["files ignored"]) == 0
    assert len(res[1]["directories empty"]) == 0


if __name__ == "__main__":
    # Run all tests
    loc = locals()
    for key in list(loc.keys()):
        if key.startswith("test_") and hasattr(loc[key], "__call__"):
            loc[key]()
