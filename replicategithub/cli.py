import click
import logging
import multiprocessing
import os
import signal
import sys
import yaml

import replicategithub

def set_up_logging(level=logging.WARNING, library_level=logging.WARNING):
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

    logging.getLogger("github").setLevel(library_level)
    multiprocessing.log_to_stderr().setLevel(library_level)

def get_async_mirror(config):
    mirror = replicategithub.Mirror(
        config["mirror_path"], config["github_user"], config["github_token"])
    return replicategithub.AsyncMirror(mirror, worker_count=config["workers"])

class Config(dict):
    pass
pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('--workers', '-j', type=int, default=None, metavar="COUNT",
    help="Number of git subprocesses to use (default 1).")
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--debug', '-d', default=False, is_flag=True)
@click.option('--config-file', '-c', type=click.File('rt'),
    default="/etc/replicate-github.yaml")
@click.version_option()
@click.pass_context
def main(context, workers, verbose, debug, config_file):
    """
    Mirror GitHub repositories.

    \b
      * Mirror arbitrary GitHub repositories.
      * Mirror all GitHub repositories under an organization.
      * Serve webhook endpoints to update mirrors automatically.
    """

    config = context.ensure_object(Config)
    config.update(yaml.safe_load(config_file.read()))
    config_file.close()

    if workers is not None:
        config['workers'] = workers
    if 'workers' not in config:
        config['workers'] = 1

    context.default_map = config

    if debug:
        level = logging.DEBUG
        library_level = logging.INFO
    elif verbose:
        level = logging.INFO
        library_level = logging.WARNING
    else:
        level = logging.WARNING
        library_level = logging.WARNING

    set_up_logging(level)

@main.command()
@click.argument("matches", metavar="ORG/REPO [ORG/REPO ...]", required=True, nargs=-1)
@pass_config
def mirror(config, matches):
    """ Create or update repo mirrors. """

    logger = logging.getLogger("mirror")
    mirror = get_async_mirror(config)

    for match in matches:
        # Friendly error message for likely mistake
        parts = match.split("/")
        if len(parts) != 2 or parts[0] == "*":
            for child in multiprocessing.active_children():
                child.terminate()
            raise click.ClickException(
                "'{}' does not match owner/repo or owner/*".format(match))

        if parts[1] == "*":
            mirror.mirror_org(parts[0])
        else:
            mirror.mirror_repo(match)

    mirror.stop()

@main.command()
@click.option('--older-than', type=int, default=24*60*60, metavar="SECONDS",
    help="Cut off age in seconds (default 86400).")
@pass_config
def freshen(config, older_than):
    """ Update oldest repos in mirror. """

    logger = logging.getLogger("freshen")
    logger.info("Freshening repos")

    mirror = get_async_mirror(config)
    mirror.update_old_repos(older_than)
    mirror.stop()

@main.command(name="sync-org")
@click.argument("orgs", metavar="ORG [ORG ...]", required=True, nargs=-1)
@pass_config
def sync_org(config, orgs):
    """
    Add and delete mirrors to match GitHub.

    This does not update mirrors that haven't been added or deleted. Use the
    mirror command, or combine this with freshen.
    """

    logger = logging.getLogger("sync-org")
    mirror = get_async_mirror(config)

    for org in orgs:
        logger.info("Syncing {} organization".format(org))
        mirror.sync_org(org)

    mirror.stop()

@main.command()
@click.option('--listen', '-l', default="localhost", metavar="ADDRESS",
    help="Address to listen on (default localhost).")
@click.option('--port', '-p', type=int, default=8080, metavar="PORT",
    help="Port to listen on (default 8080).")
@click.option('--secret', metavar="STRING",
    help="Secret to authenticate Github")
@pass_config
def serve(config, listen, port, secret):
    """ Serve webhook endpoint for GitHub. """

    logger = logging.getLogger("serve")
    logger.info("Serving HTTP on {}:{}".format(listen, port))

    replicategithub.webhook.serve(
        get_async_mirror(config),
        secret,
        (listen, port))
