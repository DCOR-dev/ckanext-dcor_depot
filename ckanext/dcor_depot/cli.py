import datetime
import pathlib
import time
import traceback as tb

import ckan.logic as logic
import ckan.model as model
import click

from dcor_shared import (
    DC_MIME_TYPES, s3, s3cc, get_resource_info, sha256sum
)

from . import app_res
from .figshare import figshare
from . import jobs


def click_echo(message, am_on_a_new_line):
    if not am_on_a_new_line:
        click.echo("")
    click.echo(message)


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
    dataset_dict = package_show(context={'ignore_auth': True,
                                         'user': 'default'},
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


@click.command()
@click.option("--modified-days", default=-1,
              help="Only migrate datasets modified within this number of days "
                   + "in the past. Set to -1 to apply to all datasets.")
@click.option("--delete-after-migration", is_flag=True,
              help="Delete files from local block storage after successful "
                   "transfer to object storage.")
@click.option("--verify-existence", is_flag=True,
              help="Verify that resources exist in S3")
@click.option("--verify-checksum", is_flag=True,
              help="Verify the checksum of the file in S3; this option "
                   "implies --verify-existence")
def dcor_migrate_resources_to_object_store(modified_days=-1,
                                           delete_after_migration=False,
                                           verify_existence=False,
                                           verify_checksum=False,
                                           ):
    """Migrate resources on block storage to an S3-compatible object store

    This also happens for draft datasets.
    """
    # verify_checksum implies verify_existence [sic]
    verify_existence = verify_existence or verify_checksum
    # go through all datasets
    datasets = model.Session.query(model.Package)

    if modified_days >= 0:
        # Search only the last `days` days.
        past = datetime.date.today() - datetime.timedelta(days=modified_days)
        past_str = time.strftime("%Y-%m-%d", past.timetuple())
        datasets = datasets.filter(model.Package.metadata_modified >= past_str)

    nl = False
    for dataset in datasets:
        nl = False
        click.echo(f"Migrating dataset {dataset.id}\r", nl=False)
        for resource in dataset.resources:
            rid = resource.id
            ds_dict, res_dict = get_resource_info(rid)
            rid = res_dict["id"]
            res_loc = str(jobs.get_resource_path(rid))
            for artifact, suffix, obj_sha in [
                ("resource", "", res_dict.get("sha256")),
                ("preview", "_preview.jpg", None),
                    ("condensed", "_condensed.rtdc", None)]:
                if not res_dict.get("s3_available", False) or verify_existence:
                    local_path = res_loc + suffix
                    # Only continue if the local file exists
                    if pathlib.Path(local_path).exists():
                        # compute sha256sum if not available
                        obj_sha = obj_sha or sha256sum(local_path)
                        override = False  # no override by default

                        if verify_checksum and s3cc.artifact_exists(
                                rid, artifact=artifact):
                            s3_sha256 = s3cc.compute_checksum(
                                rid, artifact=artifact)
                            if s3_sha256 != obj_sha:
                                # Override only if the user requested it and
                                # only if the SHA256 sum did not match.
                                override = True
                        try:
                            s3_url = s3cc.upload_artifact(
                                resource_id=rid,
                                path_artifact=local_path,
                                artifact=artifact,
                                sha256=obj_sha,
                                private=ds_dict["private"],
                                override=override,
                            )
                            if verify_checksum:
                                click_echo(f"Verified {artifact} {rid}", nl)
                            elif verify_existence:
                                click_echo(f"Checked {artifact} {rid}", nl)
                            else:
                                click_echo(f"Uploaded {artifact} {rid}", nl)
                            nl = True
                        except FileNotFoundError:
                            click_echo(f"Missing file {local_path}", nl)
                            nl = True
                        else:
                            # Only ever delete when upload succeeds
                            if delete_after_migration:
                                pathlib.Path(local_path).unlink()
                                path_res = pathlib.Path(local_path).resolve()
                                if path_res.exists():
                                    path_res.unlink()

                            # Check if the s3 URLs have been set
                            if (artifact == "resource"
                                and ("s3_available" not in res_dict
                                     or "s3_url" not in res_dict)):
                                try:
                                    # Update the resource dictionary
                                    logic.get_action("resource_patch")(
                                        context={
                                            # https://github.com/ckan/
                                            # ckan/issues/7787
                                            "user": ds_dict["creator_user_id"],
                                            "ignore_auth": True},
                                        data_dict={"id": rid,
                                                   "s3_available": True,
                                                   "s3_url": s3_url})
                                except BaseException:
                                    click_echo(
                                        f"Failed resource {resource.name}", nl)
                                    nl = True
                                    click_echo(tb.format_exc(), nl)

    if not nl:
        click.echo("")
    click.echo("Done!")


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


# TODO: Remove this method (it should not be used in current workflows)
@click.command()
@click.option('--modified-days', default=-1,
              help='Only run for datasets modified within this number of days '
                   + 'in the past. Set to -1 to apply to all datasets.')
def run_jobs_dcor_depot(modified_days=-1):
    """Run all jobs of the dcor_depot extension

    This also happens for draft datasets.
    """
    # go through all datasets
    datasets = model.Session.query(model.Package)

    if modified_days >= 0:
        # Search only the last `days` days.
        past = datetime.date.today() - datetime.timedelta(days=modified_days)
        past_str = time.strftime("%Y-%m-%d", past.timetuple())
        datasets = datasets.filter(model.Package.metadata_modified >= past_str)

    nl = False  # new line character
    for dataset in datasets:
        nl = False
        click.echo(f"Checking dataset {dataset.id}\r", nl=False)
        ds_dict = dataset.as_dict()
        ds_dict["organization"] = logic.get_action("organization_show")(
                {'ignore_auth': True}, {"id": dataset.owner_org})
        for resource in dataset.resources:
            res_dict = resource.as_dict()
            try:
                if jobs.job_migrate_resource_to_s3(resource=res_dict):
                    click_echo(f"Migrated to S3 {resource.name}", nl)
                    nl = True
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                click_echo(
                    f"{e.__class__.__name__}: {e} for {resource.name}", nl)
                nl = True
    if not nl:
        click.echo("")
    click.echo("Done!")


def get_commands():
    return [append_resource,
            dcor_import_figshare,
            dcor_list_s3_objects_for_dataset,
            dcor_migrate_resources_to_object_store,
            dcor_prune_stale_multipart_uploads,
            list_all_resources,
            run_jobs_dcor_depot,
            ]
