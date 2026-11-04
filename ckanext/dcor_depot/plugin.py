from ckan import config
import ckan.plugins as plugins

from .cli import get_commands


class DCORDepotPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IClick, inherit=True)
    plugins.implements(plugins.IConfigDeclaration, inherit=True)

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
