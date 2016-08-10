import git
import github
from glob import iglob
import logging
import multiprocessing
import os
import re
import time

from replicategithub import webhook

def validate_repo_name(full_name):
    """
    Fail if the passed full repo name is invalid

    This is my best guess at what GitHub supports.

    This is important for security, a repo name with a "../" or starting with
    "/" could result in access outside of the mirror directory.
    """
    # Best guess at GitHub repo name format
    legal_name = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    name_re = re.compile("^{0}/{0}$".format(legal_name))
    if not name_re.match(full_name):
        raise Exception("Illegal repo name: '{}'".format(full_name))

def get_organization_repos(token, organization_name):
    """ Get repos in a given organization from GitHub """
    return github.Github(token)\
        .get_organization(organization_name)\
        .get_repos()

try:
    from click import ClickException
    class MirrorException(ClickException):
        pass
except ImportError:
    class MirrorException(Exception):
        pass

class Mirror:
    """
    A GitHub mirror

    This is a directory with contents following the GitHub scheme. For example,
    it might contain danielparks/replicate-github.git.
    """
    def __init__(self, path, username, token):
        self.path = path
        self.username = username
        self.token = token
        self.logger = logging.getLogger("Mirror")
        if not os.path.isdir(path):
            raise MirrorException("Mirror directory {} not found".format(path))

    def get_repo_path(self, full_name):
        return "{}/{}.git".format(self.path, full_name)

    def get_clone_url(self, full_name):
        return "https://{}:{}@github.com/{}.git".format(
            self.username, self.token, full_name)

    def initialize_repo(self, full_name):
        path = self.get_repo_path(full_name)
        if os.path.exists(path):
            raise MirrorException("Cannot init repo; path exists: {}".format(path))

        self.logger.info("Initializing {}".format(full_name))

        organization_path = os.path.dirname(path)
        if not os.path.exists(organization_path):
            os.mkdir(organization_path, 0o755)

        git.Repo.init(path, bare=True).git.remote(
            "add", "--mirror", "origin", self.get_clone_url(full_name))

    def fetch_repo(self, full_name):
        path = self.get_repo_path(full_name)
        if not os.path.exists(path):
            self.initialize_repo(full_name)

        self.logger.info("Fetching {}".format(full_name))

        git.Repo.init(path, bare=True).git.fetch("origin")

    def delete_repo(self, full_name):
        raise MirrorException("Not implemented: delete_repo {}".format(full_name))

    def get_repo_times(self, before=None):
        if before is None:
            before = time.time() + 1000000

        for head_path in iglob("{}/*/*.git/FETCH_HEAD".format(self.path)):
            mtime = os.path.getmtime(head_path)
            if mtime < before:
                repo_name_git = "/".join(head_path.split("/")[-3:-1])
                repo_name = repo_name_git[:-4]
                yield (mtime, repo_name)

    def get_oldest_repo_names(self, before=None):
        for mtime, repo_name in sorted(self.get_repo_times(before)):
            yield repo_name

def worker(mirror, queue):
    """ Worker for AsyncMirror """
    while True:
        task = queue.get()
        if task[0] == "fetch":
            mirror.fetch_repo(task[1])
        elif task[0] == "delete":
            mirror.delete_repo(task[1])
        elif task[0] == "stop":
            return
        else:
            raise Exception("Unknown action: {}".format(action))

class AsyncMirror:
    """ A wrapper around Mirror that performs operations asynchronously """
    def __init__(self, mirror, worker_count=2):
        self.mirror = mirror
        self.queue = multiprocessing.Queue()

        self.logger = logging.getLogger("AsyncMirror")
        self.logger.info("Starting with {} workers".format(worker_count))

        for i in range(worker_count):
            multiprocessing.Process(
                target=worker,
                args=(self.mirror,self.queue)).start()

    def fetch_repo(self, repo_name):
        self.logger.debug("Adding job: fetch {}".format(repo_name))
        self.queue.put(("fetch", repo_name))

    def delete_repo(self, repo_name):
        self.logger.debug("Adding job: delete {}".format(repo_name))
        self.queue.put(("delete", repo_name))

    def fetch_old_repos(self, older_than=24*60*60):
        before = time.time() - older_than
        for repo_name in self.mirror.get_oldest_repo_names(before):
            self.logger.debug("Adding freshen job: fetch {}".format(repo_name))
            self.queue.put(("fetch", repo_name))

    def stop(self):
        self.logger.debug("Stopping all workers")
        for _ in multiprocessing.active_children():
            self.queue.put(("stop",))
        self.queue.close()
