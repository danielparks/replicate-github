from contextlib import contextmanager
import git
import github
from glob import iglob
import logging
import multiprocessing
import os
import re
import shutil
import time

from replicategithub import webhook

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

    @contextmanager
    def timed_action(self, message):
        self.logger.info(message)
        start = time.time()
        yield
        self.logger.debug("{} finished in {:.3f} seconds"
            .format(message, time.time() - start))

    def validate_name(self, partial_name):
        """
        Fail if the passed partial name is invalid

        This is my best guess at what GitHub supports.

        This is important for security, a repo name with a "../" or starting with
        "/" could result in access outside of the mirror directory.
        """
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", partial_name):
            raise Exception("Illegal name: '{}'".format(partial_name))

    def validate_repo_name(self, full_name):
        """
        Fail if the passed full repo name (ORG/REPO) is invalid

        See validate_name()
        """
        try:
            for part in full_name.split("/", 2):
                self.validate_name(part)
        except:
            raise Exception("Illegal repo name: '{}'".format(full_name))

    def validate_match(self, match):
        """
        Fail if the passed repo match (ORG/REPO, ORG/*, */*, etc.) is invalid

        See validate_name()
        """
        try:
            for part in match.split("/", 2):
                if part != "*":
                    self.validate_name(part)
        except:
            raise Exception("Illegal repo match: '{}'".format(match))

    def get_repo_path(self, full_name):
        self.validate_repo_name(full_name)
        return "{}/{}.git".format(self.path, full_name)

    def get_clone_url(self, full_name):
        return "https://{}:{}@github.com/{}.git".format(
            self.username, self.token, full_name)

    def get_mirror_names(self, match="*/*"):
        self.validate_match(match)
        for path in iglob("{}/{}.git".format(self.path, match)):
            # Strip the path prefix and the ".git"
            yield path[len(self.path) + 1  : -4]

    def get_mirror_names_set(self, match="*/*"):
        with self.timed_action("Getting {} mirrors".format(match)):
            return set(self.get_mirror_names(match))

    def get_org_repos(self, org):
        """ Get repos in a given organization from GitHub """
        repos = github.Github(self.token) \
            .get_organization(org) \
            .get_repos()
        for repo in repos:
            yield repo.full_name

    def get_org_repos_set(self, org):
        """ Get repos in a given organization from GitHub as a set """
        with self.timed_action("Getting GitHub {} repos".format(org)):
            return set(self.get_org_repos(org))

    def initialize_repo(self, full_name):
        path = self.get_repo_path(full_name)
        if os.path.exists(path):
            raise MirrorException("Cannot init repo; path exists: {}".format(path))

        with self.timed_action("Initializing {}".format(full_name)):
            org_path = os.path.dirname(path)
            if not os.path.exists(org_path):
                os.mkdir(org_path, 0o755)

            git.Repo.init(path, bare=True).git.remote(
                "add", "--mirror", "origin", self.get_clone_url(full_name))

    def mirror_repo(self, full_name):
        path = self.get_repo_path(full_name)
        if not os.path.exists(path):
            self.initialize_repo(full_name)

        with self.timed_action("Fetching {}".format(full_name)):
            git.Repo.init(path, bare=True).git.fetch("origin")

    def delete_repo(self, full_name):
        path = self.get_repo_path(full_name)
        if not os.path.exists(path):
            self.logger.debug("Repo {} already deleted".format(full_name))
            return

        with self.timed_action("Deleting {}".format(full_name)):
            target = "{}/.{}.delete.{}".format(
                os.path.dirname(path), os.path.basename(path), os.getpid())
            os.rename(path, target)
            shutil.rmtree(target)

    def get_mirror_times(self, before=None):
        if before is None:
            before = time.time() + 1000000

        for repo_name in self.get_mirror_names():
            mtime = os.path.getmtime(
                "{}/{}.git/FETCH_HEAD".format(self.path, repo_name))
            if mtime < before:
                yield (mtime, repo_name)

    def get_oldest_repo_names(self, before=None):
        for mtime, repo_name in sorted(self.get_mirror_times(before)):
            yield repo_name

def worker_handle_task(mirror, queue, action, values):
    if action == "mirror":
        mirror.mirror_repo(values[0])
    elif action == "delete":
        mirror.delete_repo(values[0])
    elif action == "mirror_org":
        org = values[0]
        repos = mirror.get_org_repos_set(org)
        mirrors = mirror.get_mirror_names_set("{}/*".format(org))

        for repo_name in repos:
            queue.put(("mirror", repo_name))
        for repo_name in mirrors - repos:
            queue.put(("delete", repo_name))
    elif action == "sync_org":
        org = values[0]
        repos = mirror.get_org_repos_set(org)
        mirrors = mirror.get_mirror_names_set("{}/*".format(org))

        for repo_name in repos - mirrors:
            print("sync mirror {}".format(repo_name))
            queue.put(("mirror", repo_name))
        for repo_name in mirrors - repos:
            print("sync delete {}".format(repo_name))
            queue.put(("delete", repo_name))
    elif action == "stop":
        raise StopIteration()
    else:
        raise Exception("Unknown action: {}".format(action))

def worker(mirror, queue):
    """ Worker for AsyncMirror """
    try:
        while True:
            task = queue.get()
            try:
                worker_handle_task(mirror, queue, task[0], task[1:])
            finally:
                queue.task_done()
    except KeyboardInterrupt:
        return

class AsyncMirror:
    """ A wrapper around Mirror that performs operations asynchronously """
    def __init__(self, mirror, worker_count=2):
        self.mirror = mirror
        self.queue = multiprocessing.JoinableQueue()

        self.logger = logging.getLogger("AsyncMirror")
        self.logger.info("Starting with {} workers".format(worker_count))

        for i in range(worker_count):
            multiprocessing.Process(
                target=worker,
                args=(self.mirror,self.queue)).start()

    def mirror_repo(self, repo_name):
        self.logger.debug("Adding job: mirror {}".format(repo_name))
        self.queue.put(("mirror", repo_name))

    def delete_repo(self, repo_name):
        self.logger.debug("Adding job: delete {}".format(repo_name))
        self.queue.put(("delete", repo_name))

    def mirror_org(self, org):
        self.logger.debug("Adding job: mirror org {}".format(org))
        self.queue.put(("mirror_org", org))

    def sync_org(self, org):
        self.logger.debug("Adding sync job: {}".format(org))
        self.queue.put(("sync_org", org))

    def update_old_repos(self, older_than=24*60*60):
        before = time.time() - older_than
        for repo_name in self.mirror.get_oldest_repo_names(before):
            self.logger.debug("Adding freshen job: update {}".format(repo_name))
            self.queue.put(("mirror", repo_name))

    def stop(self):
        self.logger.debug("Stopping all workers")
        self.queue.join()
        for child in multiprocessing.active_children():
            child.terminate()
        self.queue.close()
