import pathlib

import ckan.logic as logic
import ckan.model as model
import click

from dcor_shared import DC_MIME_TYPES, s3, s3cc

from . import app_res
from .figshare import figshare


@click.command()
@click.argument('path')
@click.argument('dataset_id')
@click.option('--delete-source', is_flag=True,
              help='Delete the original local file')
def append_resource(path, dataset_id, delete_source=False):
    """Append a resource to a dataset

    This can be done even after the dataset is made active.
    It can be used to e.g. append post-processed DC data to an
    existing dataset.

    Pass the path `path` to a resource, and it will be added to the
    specified `dataset_id` (id or name).
    """
    path = pathlib.Path(path)
    app_res.append_resource(path=path,
                            dataset_id=dataset_id,
                            delete_source=delete_source)


@click.command()
@click.option('--limit', default=0, help='Limit number of datasets imported')
def dcor_import_figshare(limit):
    """Import a predefined list of datasets from figshare"""
    figshare(limit=limit)


@click.command()
@click.argument('dataset_id')
def dcor_list_s3_objects_for_dataset(dataset_id):
    """List S3 resource and other data locations for a dataset

    The resources are printed as "bucket:path (message)" and the
    colors indicate whether the object is publicly available (green),
    private (blue), or not there (red).
    """
    package_show = logic.get_action("package_show")
    dataset_dict = package_show(context=app_res.admin_context(),
                                data_dict={"id": dataset_id})
    # For each resource, list the objects that are currently in S3 along
    # with the S3 object tags.
    for res_dict in dataset_dict["resources"]:
        rid = res_dict["id"]
        bucket_name, object_name = s3cc.get_s3_bucket_object_for_artifact(
            rid, artifact="resource")
        paths = [object_name]
        if res_dict["mimetype"] in DC_MIME_TYPES:
            paths.append(s3cc.get_s3_bucket_object_for_artifact(
                rid, artifact="condensed")[1])
            paths.append(s3cc.get_s3_bucket_object_for_artifact(
                rid, artifact="preview")[1])
        s3_client, _, _ = s3.get_s3()
        for pp in paths:
            try:
                response = s3_client.get_object_tagging(
                    Bucket=bucket_name,
                    Key=pp)
                tags = []
                for item in response["TagSet"]:
                    tags.append(f"{item['Key']}={item['Value']}")
                if tags.count("public=true"):
                    # As mentioned in the s3 submodule, we define public
                    # access by the presence of the "public=true" tag for
                    # an object.
                    color = "green"
                else:
                    color = "blue"
                    tags.append("PRIVATE")
                message = " ".join(tags)
            except s3_client.exceptions.NoSuchKey:
                color = "red"
                message = "not found"
            click.secho(f"{bucket_name}:{pp} ({message})", fg=color)


@click.option('--initiated-before-days', default=5,
              help='Only prune multipart uploads that were initiated '
                   + 'before a given number of days (set to -1 to prune all)')
@click.option('--dry-run', is_flag=True,
              help='Do not prune, only print what would happen')
@click.command()
def dcor_prune_stale_multipart_uploads(initiated_before_days=5, dry_run=False):
    """Prune stale multipart uploads

    When users upload data to DCOR and the upload is aborted unexpectedly,
    then stale multipart uploads might still be around. These multipart
    uploads normally count against the storage quota and can incur costs.
    Pruning them is a sensible task that should be done regularly.
    """
    prune_info = s3.prune_multipart_uploads(
        initiated_before_days=initiated_before_days,
        dry_run=dry_run,
        print_progress=True,
    )
    # assemble and print stats
    num_buckets = 0
    num_found = 0
    num_ignored = 0
    for bucket_name in prune_info.keys():
        bd = prune_info[bucket_name]
        num_found += bd["found"]
        num_ignored += bd["ignored"]
        if bd["found"] and bd["ignored"]:
            num_buckets += 1
    click.echo(f"Affected buckets: {num_buckets}")
    click.echo(f"Stale uploads found: {num_found}")
    click.echo(f"Ignored recent uploads: {num_ignored}")
    click.echo("Done!")


@click.command()
def list_all_resources():
    """List all (public and private) resource IDs"""
    datasets = model.Session.query(model.Package)
    for dataset in datasets:
        for resource in dataset.resources:
            click.echo(resource.id)


def get_commands():
    return [append_resource,
            dcor_import_figshare,
            dcor_list_s3_objects_for_dataset,
            dcor_prune_stale_multipart_uploads,
            list_all_resources,
            ]
