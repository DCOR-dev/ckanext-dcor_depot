import click

from .figshare import figshare


@click.command()
@click.option('--limit', default=0, help='Limit number of datasets imported')
def import_figshare(limit):
    figshare(limit=limit)


def get_commands():
    return [import_figshare]
