import ckan.plugins as p
import ckan.plugins.toolkit as toolkit

from .cli import get_commands
from .jobs import symlink_user_dataset


class DCORDepotPlugin(p.SingletonPlugin):
    p.implements(p.IClick)
    p.implements(p.IResourceController, inherit=True)

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
        toolkit.enqueue_job(symlink_user_dataset,
                            [pkg, usr, resource],
                            title="Move and symlink user dataset",
                            rq_kwargs={"timeout": 60})
