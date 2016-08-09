import click
import logging
import os
import signal
import sys
import yaml

import replicategithub

config = None
mirror = None

def set_up_logging(level=logging.WARNING):
    logging.captureWarnings(True)

    handler = logging.StreamHandler(stream=sys.stdout)
    try:
        import colorlog
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(name)s: %(message)s'))
    except ImportError:
        handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

@click.group()
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--config-file', '-c', type=click.File('rt'),
    default="/etc/replicate-github.yaml")
def main(verbose, config_file):
    global config, mirror

    if verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    config = yaml.safe_load(config_file.read())
    config_file.close()

    mirror = replicategithub.Mirror(
        config["mirror_path"], config["github_user"], config["github_token"])

    set_up_logging(level)

@main.command()
@click.argument("repos", metavar="ORG/REPO [ORG/REPO ...]", required=True, nargs=-1)
def fetch(repos):
    """ Fetch repos into the mirror """
    global mirror
    logger = logging.getLogger("fetch")

    for repo_name in repos:
        parts = repo_name.split("/")

        # Friendly error message for likely mistake
        if len(parts) != 2:
            sys.exit("Repo name '{}' does not match format owner/repo or owner/*"
                .format(repo_name))

        if parts[1] == "*":
            for repo in replicategithub.get_organization_repos(config["github_token"], parts[0]):
                replicategithub.validate_repo_name(repo.full_name)
                mirror.fetch_repo(repo.full_name)
        else:
            replicategithub.validate_repo_name(repo_name)
            mirror.fetch_repo(repo_name)

@main.command()
@click.option('--listen', '-l', default="localhost")
@click.option('--port', '-p', type=int, default=8080)
def serve(listen, port):
    """ Serve webhook endpoint for GitHub """
    global config, mirror
    logger = logging.getLogger("serve")
    logger.info("Serving HTTP on {}:{}".format(listen, port))
    replicategithub.webhook.serve(
        mirror,
        config.get('webhook_secret', None),
        (listen, port))
