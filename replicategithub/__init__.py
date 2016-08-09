import git
import github
import logging
import os
import re

from replicategithub import webhook

def validate_repo_name(full_name):
    # Best guess at GitHub repo name format
    legal_name = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    name_re = re.compile("^{0}/{0}$".format(legal_name))
    if not name_re.match(full_name):
        raise Exception("Illegal repo name: '{}'".format(full_name))

def get_organization_repos(token, organization_name):
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
