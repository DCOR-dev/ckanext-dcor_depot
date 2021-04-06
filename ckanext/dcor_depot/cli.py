import ckan.model as model
import click

from .depotize import depotize
from .figshare import figshare
from .internal import internal, internal_upgrade


@click.command()
@click.argument('path')
@click.option('--ignore-unknown', is_flag=True,
              help='Continue when encountering unknown files')
@click.option('--no-cleanup', is_flag=True, help='By default, temporary files '
              + 'are cleaned up, which involves: removing untarred files, '
              + 'moving source tar files to /data/archive/processed/, '
              + 'and archiving processing-metadata in '
              + '/data/archive/archived_meta. Set this flag if you do not '
              + 'want these things to happen.')
@click.option('--skip-failed', is_flag=True,
              help='Skip archives that failed in previous runs')
@click.option('--verbosity', default=1, type=int,
              help='Increase for more verbosity')
def depotize_archive(path, no_cleanup=False, ignore_unknown=False,
                     skip_failed=False, verbosity=1):
    """Transform arbitrary RT-DC data to the DCOR depot file structure

    The following tasks are performed:

    - unpack the tar file to `original/path/filename.tar_depotize/data`
    - scan the unpacked directory for RT-DC data (.rtdc and .tdms);
      found datasets are written to the text file
      `original/path/filename.tar_depotize/measurements.txt`
    - check whether the data files in `measurements.txt` are valid
      and store them in `check_usable.txt`
    - convert the data to compressed .rtdc files and create condensed
      datasets

    By default, the depot data are stored in the directory root in
    `/data/depots/internal/` and follow the directory structure
    `201X/2019-08/20/2019-08-20_1126_c083de*` where the allowed file names
    in this case are

    - 2019-08-20_1126_c083de.sha256sums a file containing SHA256 sums
    - 2019-08-20_1126_c083de_v1.rtdc the actual measurement
    - 2019-08-20_1126_c083de_v1_condensed.rtdc the condensed dataset
    - 2019-08-20_1126_c083de_ad1_m001_bg.png an ancillary image
    - 2019-08-20_1126_c083de_ad2_m002_bg.png another ancillary image

    You may run this command for individual archives:

       ckan depotize-archive /path/to/archive.tar

    or recursively for entire directory trees

       ckan depotize-archive /path/to/directory/
    """
    depotize(path,
             cleanup=not no_cleanup,
             abort_on_unknown=not ignore_unknown,
             skip_failed=skip_failed,
             verbose=verbosity)


@click.command()
@click.option('--limit', default=0, help='Limit number of datasets imported')
def import_figshare(limit):
    """Import a predefined list of datasets from figshare"""
    figshare(limit=limit)


@click.command()
@click.option('--limit', default=0, help='Limit number of datasets imported')
@click.option('--start-date', default="2000-01-01",
              help='Import datasets in the depot starting from a given date')
@click.option('--end-date', default="3000-01-01",
              help='Import datasets in the depot only until a given date')
def import_internal(limit, start_date="2000-01-01", end_date="3000-01-01"):
    """Import internal data located in /data/depots/internal"""
    internal(limit=limit, start_date=start_date, end_date=end_date)


@click.command()
@click.option('--start-date', default="2000-01-01",
              help='Search for upgraded resources in the depot starting '
                   + 'from a given date')
@click.option('--end-date', default="3000-01-01",
              help='Search for upgraded resources in the depot '
                   + 'only until a given date')
def upgrade_internal(start_date="2000-01-01", end_date="3000-01-01"):
    """Upgrade resource versions located in /data/depots/internal in CKAN

    If you are running this command, you should have already created
    new versions of resources (i.e. date-something_v2.rtdc next to
    a date-something_v1.rtdc file).

    During upgrade, the condensed version of the resource
    (date-something_v2_condensed.rtdc) will be created and the SHA256
    sums file will be updated. Then, the resource will be added to
    the original dataset.
    """
    internal_upgrade(start_date=start_date, end_date=end_date)


@click.command()
def list_all_resources():
    """List all (public and private) resource ids"""
    datasets = model.Session.query(model.Package)
    for dataset in datasets:
        for resource in dataset.resources:
            click.echo(resource.id)


def get_commands():
    return [depotize_archive,
            import_figshare,
            import_internal,
            upgrade_internal,
            list_all_resources]
