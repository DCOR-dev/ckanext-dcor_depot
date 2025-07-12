from ckan import config
import ckan.plugins as plugins

from dcor_shared import s3

from .cli import get_commands
from . import jobs


class DCORDepotPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IClick, inherit=True)
    plugins.implements(plugins.IConfigDeclaration, inherit=True)
    plugins.implements(plugins.IResourceController, inherit=True)

    # IClick
    def get_commands(self):
        return get_commands()

    # IConfigDeclaration
    def declare_config_options(
            self,
            declaration: config.declaration.Declaration,
            key: config.declaration.Key):

        dcor_depot_group = key.ckanext.dcor_depot

        declaration.declare(dcor_depot_group.tmp_dir).set_description(
            "temporary directory for importing resource files"
        )

    # IResourceController
    def after_resource_create(self, context, resource):
        if not context.get("is_background_job") and s3.is_available():
            # All jobs are defined via decorators in jobs.py
            jobs.RQJob.enqueue_all_jobs(resource, ckanext="dcor_depot")
