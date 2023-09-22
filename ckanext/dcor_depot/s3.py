import functools
import hashlib
import pathlib

import boto3

from dcor_shared import get_ckan_config_option


@functools.lru_cache()
def get_s3():
    """Return the current S3 client as defined by ckan.ini"""
    # Create a new session (do not use the default session)
    s3_session = boto3.Session(
        aws_access_key_id=get_ckan_config_option(
            "dcor_object_store.access_key_id"),
        aws_secret_access_key=get_ckan_config_option(
            "dcor_object_store.secret_access_key"),
    )
    ssl_verify = get_ckan_config_option(
        "dcor_object_store.ssl_verify").lower() == "true"
    s3_client = s3_session.client(
        service_name='s3',
        use_ssl=ssl_verify,
        verify=ssl_verify,
        endpoint_url=get_ckan_config_option("dcor_object_store.endpoint_url"),
    )
    s3_resource = s3_session.resource(
        service_name="s3",
        use_ssl=ssl_verify,
        verify=ssl_verify,
        endpoint_url=get_ckan_config_option("dcor_object_store.endpoint_url"),
    )
    return s3_client, s3_session, s3_resource


@functools.lru_cache()
def require_bucket(bucket_name):
    """Create an S3 bucket if it does not exist yet

    Parameters
    ----------
    bucket_name: str
        Bucket to create
    """
    _, _, s3_resource = get_s3()
    # Create the bucket (this will return the bucket if it already exists)
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/
    # services/s3/client/create_bucket.html
    s3_bucket = s3_resource.Bucket(bucket_name)
    if s3_bucket.creation_date is None:
        s3_bucket.create()
    return s3_bucket


def upload_file(bucket_name, object_name, path, sha256, private=True):
    s3_client, _, _ = get_s3()
    s3_bucket = require_bucket(bucket_name)
    s3_bucket.upload_file(Filename=str(path),
                          Key=object_name,
                          ExtraArgs={
                              # private or public resource?
                              "ACL": "private" if private else "public-read",
                              # verification of the upload
                              "ChecksumAlgorithm": "SHA256",
                              # This is not supported in MinIO:
                              # "ChecksumSHA256": sha256
                          })
    # Make sure the upload worked properly by computing the SHA256 sum.
    # Download the file directly into the hasher.
    hasher = hashlib.sha256()
    increment = 2**20
    start_byte = 0
    max_size = pathlib.Path(path).stat().st_size
    stop_byte = min(increment, max_size)
    while start_byte < max_size:
        resp = s3_client.get_object(Bucket=bucket_name,
                                    Key=object_name,
                                    Range=f"bytes={start_byte}-{stop_byte}")
        content = resp['Body'].read()
        if not content:
            break
        hasher.update(content)
        start_byte = stop_byte
        stop_byte = min(max_size, stop_byte + increment)
    s3_sha256 = hasher.hexdigest()
    if sha256 != s3_sha256:
        raise ValueError("Checksums don't match!")
