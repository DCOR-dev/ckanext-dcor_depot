from ckan.lib.jobs import _connect as ckan_jobs_connect
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from rq.job import Job

from dcor_shared import s3

from .cli import get_commands
from . import jobs


class DCORDepotPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IClick, inherit=True)
    plugins.implements(plugins.IResourceController, inherit=True)

    # IClick
    def get_commands(self):
        return get_commands()

    # IResourceController
    def after_resource_create(self, context, resource):
        if not context.get("is_background_job") and s3.is_available():
            # All jobs are defined via decorators in jobs.py
            jobs.RQJob.enqueue_all_jobs(resource, ckanext="dcor_depot")

        # TODO: Remove this and make sure everything still works.
        # Symlinking new dataset
        # check organization
        pkg_id = resource["package_id"]
        pkg = toolkit.get_action('package_show')(context, {'id': pkg_id})
        # user name
        usr_id = pkg["creator_user_id"]
        usr = toolkit.get_action('user_show')(context, {'id': usr_id})
        # resource path
        pkg_job_id = f"{resource['package_id']}_{resource['position']}_"
        jid_symlink = pkg_job_id + "symlink"
        if not Job.exists(jid_symlink, connection=ckan_jobs_connect()):
            toolkit.enqueue_job(jobs.job_symlink_user_dataset,
                                [pkg, usr, resource],
                                title="Move and symlink user dataset",
                                queue="dcor-short",
                                rq_kwargs={"timeout": 60,
                                           "job_id": jid_symlink})
