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

class MirrorException(Exception):
    pass

class Collection:
    """
    A collection of GitHub mirrors

    This manages a directory with contents following the GitHub scheme. For
    example, it might contain danielparks/replicate-github.git.
    """
    def __init__(self, path, user, token):
        self.path = path
        self.user = user
        self.token = token
        self.logger = logging.getLogger("mirror.Collection")
        if not os.path.isdir(path):
            raise MirrorException("Mirror directory '{}' not found".format(path))

    @contextmanager
    def timed_action(self, message, level=logging.INFO):
        self.logger.log(level, message)
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
            raise MirrorException("Illegal name: '{}'".format(partial_name))

    def validate_repo_name(self, full_name):
        """
        Fail if the passed full repo name (ORG/REPO) is invalid

        See validate_name()
        """
        try:
            for part in full_name.split("/", 2):
                self.validate_name(part)
        except:
            raise MirrorException("Illegal repo name: '{}'".format(full_name))

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
            raise MirrorException("Illegal repo match: '{}'".format(match))

    def get_mirror_path(self, full_name):
        self.validate_repo_name(full_name)
        return "{}/{}.git".format(self.path, full_name)

    def get_clone_url(self, full_name):
        return "https://{}:{}@github.com/{}.git".format(
            self.user, self.token, full_name)

    def get_mirror_names(self, match="*/*"):
        self.validate_match(match)
        for path in iglob("{}/{}.git".format(self.path, match)):
            # Strip the path prefix and the ".git"
            yield path[len(self.path) + 1  : -4]

    def get_mirror_names_set(self, match="*/*"):
        with self.timed_action("Getting {} local mirrors".format(match),
                level=logging.DEBUG):
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
        with self.timed_action("Getting {}/* repos from GitHub".format(org),
                level=logging.DEBUG):
            return set(self.get_org_repos(org))

    def initialize_mirror(self, full_name):
        self.logger.debug("Initializing {}".format(full_name))

        path = self.get_mirror_path(full_name)
        if os.path.exists(path):
            raise MirrorException("Cannot init mirror; path exists: {}".format(path))

        org_path = os.path.dirname(path)
        if not os.path.exists(org_path):
            os.mkdir(org_path, 0o755)

        git.Repo.init(path, bare=True).git.remote(
            "add", "--mirror", "origin", self.get_clone_url(full_name))

    def mirror_repo(self, full_name):
        path = self.get_mirror_path(full_name)
        if not os.path.exists(path):
            self.initialize_mirror(full_name)

        with self.timed_action("Fetching {}".format(full_name)):
            git.Repo.init(path, bare=True).git.fetch("origin")

    def delete_mirror(self, full_name):
        path = self.get_mirror_path(full_name)
        if not os.path.exists(path):
            self.logger.debug("Mirror {} already deleted".format(full_name))
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

    def get_oldest_mirrors(self, before=None):
        for mtime, repo_name in sorted(self.get_mirror_times(before)):
            yield repo_name

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['logger']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        process_name = multiprocessing.current_process().name
        self.logger = logging.getLogger("mirror.Collection")
