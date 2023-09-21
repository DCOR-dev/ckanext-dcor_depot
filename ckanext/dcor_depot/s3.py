import functools

import boto3

from dcor_shared import get_ckan_config_option


@functools.lru_cache()
def get_s3_client():
    """Return the current S3 client as defined by ckan.ini"""
    # Create a new session (do not use the default session)
    session = boto3.Session()
    ssl_verify = get_ckan_config_option(
        "dcor_object_store.ssl_verify").lower() == "true"
    s3_client = session.client(
        service_name='s3',
        use_ssl=ssl_verify,
        verify=ssl_verify,
        api_version=get_ckan_config_option("dcor_object_store.version"),
        endpoint_url=get_ckan_config_option("dcor_object_store.endpoint_url"),
        aws_access_key_id=get_ckan_config_option(
            "dcor_object_store.access_key_id"),
        aws_secret_access_key=get_ckan_config_option(
            "dcor_object_store.secret_access_key"),
    )
    return s3_client


@functools.lru_cache()
def require_bucket(bucket_name):
    """Create an S3 bucket if it does not exist yet

    Parameters
    ----------
    bucket_name: str
        Bucket to create
    """
    s3_client = get_s3_client()
    # Create the bucket (this will return the bucket if it already exists)
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/
    # services/s3/client/create_bucket.html
    s3_bucket = s3_client.create_bucket(Bucket=bucket_name)
    return s3_bucket


def upload_file(bucket_name, object_name, path, sha256, private=True):
    s3_bucket = require_bucket(bucket_name)
    s3_bucket.upload_file(Filename=str(path),
                          Key=object_name,
                          ExtraArgs={
                              # private or public resource?
                              "ACL": "private" if private else "public-read",
                              # verification of the upload
                              "ChecksumAlgorithm": "SHA256",
                              "ChecksumSHA256": sha256}
                          )
