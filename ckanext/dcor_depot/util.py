import hashlib


def check_md5(path, md5sum, block_size=2**20):
    """Check the MD5 sum of a file"""
    file_hash = hashlib.md5()
    with path.open("rb") as fd:
        while True:
            data = fd.read(block_size)
            if not data:
                break
            file_hash.update(data)
    if file_hash.hexdigest() != md5sum:
        raise ValueError("MD5 sum mismatch for {}!".format(path))
