import ckan.model as model

import click

from .figshare import figshare
from .internal import internal


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
def list_all_resources():
    """List all (public and private) resource ids"""
    datasets = model.Session.query(model.Package)
    for dataset in datasets:
        for resource in dataset.resources:
            click.echo(resource.id)


def get_commands():
    return [import_figshare, import_internal, list_all_resources]
