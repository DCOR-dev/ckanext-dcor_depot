import ckan.plugins as plugins

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
