from functools import lru_cache
import hashlib
import pathlib

import dclab

#: Content of the dummy file created when importing data.
DUMMY_BYTES = b"[Data import pending]"


def make_id(data):
    """Return a CKAN identifier by md5summing the data

    This is used to generate reproducible dataset and resource
    identifiers.
    """
    m = hashlib.md5(obj2str(data)).hexdigest()
    return "{}-{}-{}-{}-{}".format(m[:8], m[8:12], m[12:16], m[16:20], m[20:])


def obj2str(obj):
    """String representation of an object for hashing"""
    if isinstance(obj, str):
        return obj.encode("utf-8")
    elif isinstance(obj, pathlib.Path):
        return obj2str(str(obj))
    elif isinstance(obj, (bool, int, float)):
        return str(obj).encode("utf-8")
    elif obj is None:
        return b"none"
    elif isinstance(obj, tuple):
        return obj2str(list(obj))
    elif isinstance(obj, list):
        return b"".join(obj2str(o) for o in obj)
    elif isinstance(obj, dict):
        return obj2str(sorted(obj.items()))
    else:
        raise ValueError("No rule to convert object '{}' to string.".
                         format(obj.__class__))


@lru_cache(maxsize=100)
def sha_256(path, block_size=2**20):
    return dclab.util.hashfile(path, constructor=hashlib.sha256)
