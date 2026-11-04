import hashlib
import pathlib

import pytest

from ckanext.dcor_depot import util


def test_check_md5(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("hello world")
    util.check_md5(path, hashlib.md5(b"hello world").hexdigest())
    with pytest.raises(ValueError, match="MD5 sum mismatch"):
        util.check_md5(path, hashlib.md5(b"hello").hexdigest())


def test_make_id():
    rid = util.make_id(["peter", 1, 2.5, None, True])
    # reproducible
    assert rid == util.make_id(["peter", 1, 2.5, None, True])
    assert rid != util.make_id(["peter", 1, 2.5, None, False])
    # CKAN identifier format
    assert [len(p) for p in rid.split("-")] == [8, 4, 4, 4, 12]


def test_obj2str():
    assert util.obj2str("a") == b"a"
    assert util.obj2str(pathlib.Path("a")) == b"a"
    assert util.obj2str((1, "b")) == util.obj2str([1, "b"]) == b"1b"
    # dictionaries are sorted by key
    assert util.obj2str({"b": 1, "a": 2}) == util.obj2str({"a": 2, "b": 1})
    with pytest.raises(ValueError, match="No rule to convert"):
        util.obj2str(object())
