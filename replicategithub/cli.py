import click
import logging
import multiprocessing
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
@click.option('--debug', '-d', default=False, is_flag=True)
@click.option('--config-file', '-c', type=click.File('rt'),
    default="/etc/replicate-github.yaml")
@click.version_option()
def main(verbose, debug, config_file):
    """
    Mirror GitHub repositories

    \b
      * mirror arbitrary GitHub repositories
      * mirror all GitHub repositories under an organization
      * serve webhook endpoints to update mirrors automatically
    """

    global config, mirror

    if debug:
        level = logging.DEBUG
        multiprocessing.log_to_stderr().setLevel(level)
    elif verbose:
        level = logging.INFO
        multiprocessing.log_to_stderr().setLevel(logging.WARNING)
    else:
        level = logging.WARNING
        multiprocessing.log_to_stderr().setLevel(logging.WARNING)

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
@click.option('--workers', '-j', type=int, default=2, metavar="COUNT",
    help="Number of git subprocesses to use (default: 2).")
@click.option('--older-than', type=int, default=24*60*60, metavar="SECONDS",
    help="Cut off age in seconds (default: 86400).")
def freshen(workers, older_than):
    """ Update oldest repos in mirror """
    global config, mirror

    logger = logging.getLogger("freshen")
    logger.info("Freshening repos with {} workers".format(workers))
    manager = replicategithub.AsyncMirror(mirror, worker_count=workers)
    manager.fetch_old_repos(older_than)
    manager.stop()

@main.command()
@click.option('--listen', '-l', default="localhost", metavar="ADDRESS",
    help="Address to listen on (default: localhost).")
@click.option('--port', '-p', type=int, default=8080, metavar="PORT",
    help="Port to listen on (default: 8080).")
@click.option('--workers', '-j', type=int, default=2, metavar="COUNT",
    help="Number of git subprocesses to use (default: 2).")
def serve(listen, port, workers):
    """ Serve webhook endpoint for GitHub """
    global config, mirror

    logger = logging.getLogger("serve")
    logger.info("Serving HTTP on {}:{}".format(listen, port))

    replicategithub.webhook.serve(
        replicategithub.AsyncMirror(mirror, worker_count=workers),
        config.get('webhook_secret', None),
        (listen, port))
