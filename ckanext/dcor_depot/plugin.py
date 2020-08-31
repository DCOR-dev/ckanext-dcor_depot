import ckan.plugins as p
import ckan.plugins.toolkit as toolkit

from dcor_shared import get_dataset_path

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
        path = get_dataset_path(context, resource)
        toolkit.enqueue_job(symlink_user_dataset,
                            [path, pkg, usr, resource],
                            title="Create resource preview image",
                            rq_kwargs={"timeout": 60})
