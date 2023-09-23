from ckan.lib.jobs import _connect as ckan_jobs_connect
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from rq.job import Job

from .cli import get_commands
from .jobs import symlink_user_dataset
from . import s3


class DCORDepotPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IResourceController, inherit=True)

    # IClick
    def get_commands(self):
        return get_commands()

    # IPackageController
    def after_dataset_update(self, context, data_dict):
        private = data_dict.get("private")
        if private is not None and not private:
            # Normally, we would only get here if the user specified the
            # "private" key in `data_dict`. Thus, it is not an overhead
            # for normal operations.
            # We now have a public dataset. And it could be that this
            # dataset has been private before. If we already have resources
            # in this dataset, then we have to set the S3 object tag
            # "public:true", so everyone can access it.
            orig_dict = toolkit.get_action("package_show")(
                context=context, data_dict={"id": data_dict["id"]})
            # Make sure the S3 resources get the "public:true" tag.
            bucket_name = "circle-" + orig_dict["organization"]["id"]
            for res in orig_dict["resources"]:
                if res.get("s3_available", False):
                    rid = res["id"]
                    object_names = [
                        f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}",
                    ]
                    for object_name in object_names:
                        s3.make_object_public(bucket_name=bucket_name,
                                              object_name=object_name)

    # IResourceController
    def after_resource_create(self, context, resource):
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
            toolkit.enqueue_job(symlink_user_dataset,
                                [pkg, usr, resource],
                                title="Move and symlink user dataset",
                                queue="dcor-short",
                                rq_kwargs={"timeout": 60,
                                           "job_id": jid_symlink})
