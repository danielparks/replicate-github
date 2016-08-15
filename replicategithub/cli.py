import click
import logging
import multiprocessing
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
            '%(log_color)s%(name)s[%(processName)s]: %(message)s'))
    except ImportError:
        handler.setFormatter(logging.Formatter('%(name)s[%(processName)s]: %(message)s'))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    logging.getLogger("github").setLevel(library_level)
    multiprocessing.log_to_stderr().setLevel(library_level)

class Config(dict):
    def __init__(self, *args, **kwargs):
        self.manager = None
        dict.__init__(self, *args, **kwargs)

    def get_manager(self):
        if self.manager:
            return self.manager
        self.manager = replicategithub.MirrorManager(
            path=self["mirror_path"],
            user=self["github_user"],
            token=self["github_token"],
            worker_count=self["workers"])
        return self.manager

    def stop(self):
        if self.manager:
            self.manager.stop()

pass_config = click.make_pass_decorator(Config)

def main():
    config = Config()

    try:
        try:
            cli(standalone_mode=False, obj=config)
        finally:
            config.stop()
    except click.ClickException as e:
        e.show()
        sys.exit(e.exit_code)
    except click.Abort as e:
        sys.exit(e)
    except KeyboardInterrupt:
        # Click transforms this into click.Abort, but it doesn't get the chance
        # if it's raised outside of cli() (i.e. in config.stop()).
        sys.exit(128 + signal.SIGINT)
    except replicategithub.mirror.MirrorException as e:
        sys.exit("Error: {}".format(e))

@click.group()
@click.option('--workers', '-j', type=int, default=None, metavar="COUNT",
    help="Number of git subprocesses to use (default 1).")
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--debug', '-d', default=False, is_flag=True)
@click.option('--config-file', '-c', type=click.File('rt'),
    default="/etc/replicate-github.yaml")
@click.version_option()
@pass_config
@click.pass_context
def cli(context, config, workers, verbose, debug, config_file):
    """
    Mirror GitHub repositories.

    \b
      * Mirror arbitrary GitHub repositories.
      * Mirror all GitHub repositories under an organization.
      * Serve webhook endpoints to update mirrors automatically.
    """

    config.update(yaml.safe_load(config_file.read()))
    config_file.close()

    context.default_map = config

    if workers is not None:
        config['workers'] = workers
    if 'workers' not in config:
        config['workers'] = 1

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

@cli.command()
@click.argument("matches", metavar="ORG/REPO [ORG/REPO ...]", required=True, nargs=-1)
@pass_config
def mirror(config, matches):
    """ Create or update repo mirrors. """

    for match in matches:
        # Friendly error message for likely mistakes
        parts = match.split("/")
        if len(parts) != 2 or parts[0] == "*":
            raise click.ClickException(
                "'{}' does not match owner/repo or owner/*".format(match))

        if parts[1] == "*":
            config.get_manager().mirror_org(parts[0])
        else:
            config.get_manager().mirror_repo(match)

@cli.command()
@click.option('--older-than', type=int, default=24*60*60, metavar="SECONDS",
    help="How old a mirror has to be before it's updated (default 24*60*60).")
@pass_config
def freshen(config, older_than):
    """ Update oldest repos in mirror. """

    logger = logging.getLogger("freshen")
    logger.info("Freshening repos older than {} seconds".format(older_than))

    config.get_manager().update_old_repos(older_than)

@cli.command(name="sync-org")
@click.argument("orgs", metavar="ORG [ORG ...]", required=True, nargs=-1)
@pass_config
def sync_org(config, orgs):
    """
    Add and delete mirrors to match GitHub.

    This does not update mirrors that haven't been added or deleted. Use the
    mirror command, or combine this with freshen.
    """

    logger = logging.getLogger("sync-org")

    for org in orgs:
        logger.info("Syncing {} organization".format(org))
        config.get_manager().sync_org(org)

@cli.command()
@click.option('--port', '-p', type=int, default=8080, metavar="PORT",
    help="Port to listen on (default 8080).")
@click.option('--address', default="localhost", metavar="ADDRESS",
    help="Address to listen on (default localhost).")
@click.option('--secret', metavar="STRING",
    help="Secret to authenticate Github.")
@click.option('--update-org', metavar="ORG", multiple=True,
    help="Organizations to keep in sync (default none).")
@click.option('--update-older-than', type=int, default=24*60*60, metavar="SECONDS",
    help="Ensure that all mirrors get updated at least this frequently"
        " (default 24*60*60). 0 means to only update on events.")
@click.option('--periodic-interval', type=int, default=15*60, metavar="SECONDS",
    help="How frequently to run periodic tasks (default 15*60).")
@click.option('--payload-log', type=click.File('at'), metavar="FILE",
    help="Log file for webhook payloads for debugging.")
@pass_config
def serve(config, port, address, secret, update_org, update_older_than,
        periodic_interval, payload_log):
    """
    Serve webhook endpoint for GitHub events.

    This will accept any event from GitHub with the specified secret, even if
    the event is for a repo that is not already mirrored. In other words, this
    will mirror any repo that it gets an event for, even if it doesn't already
    know about it.

    There are two options that are used to ensure updates are applied even if
    events are lost for some reason:

    \b
    --update-older-than SECONDS
        Ensure that every mirror is checked for updates at least every SECONDS.
        By default this is set to a day (86400 seconds).

    \b
    --update-org ORG
        Organizations to periodically check for new or deleted repos. May be
        specified multiple times; no organizations are synced by default.

    Neither of these options should be necessary if the webhook is set up for
    all organizations being tracked; they're an extra layer of safety.

    Both these checks run every interval specified by --periodic-interval.
    """
    replicategithub.webhook.serve(
        config.get_manager(),
        secret=secret,
        listen=(address, port),
        periodic_interval=periodic_interval,
        update_orgs=update_org,
        update_older_than=update_older_than,
        payload_log=payload_log)
