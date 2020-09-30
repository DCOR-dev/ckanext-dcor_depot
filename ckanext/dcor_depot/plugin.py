import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from .cli import get_commands
from .jobs import symlink_user_dataset


class DCORDepotPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IResourceController, inherit=True)

    # IClick
    def get_commands(self):
        return get_commands()

    # IResourceController
    def after_create(self, context, resource):
        # check organization
        pkg_id = resource["package_id"]
        pkg = toolkit.get_action('package_show')(context, {'id': pkg_id})
        # user name
        usr_id = pkg["creator_user_id"]
        usr = toolkit.get_action('user_show')(context, {'id': usr_id})
        # resource path
        jid = "-".join([resource["id"], resource["name"], "symlink"])
        toolkit.enqueue_job(symlink_user_dataset,
                            [pkg, usr, resource],
                            title="Move and symlink user dataset",
                            queue="dcor-short",
                            rq_kwargs={"timeout": 60,
                                       "job_id": jid})
