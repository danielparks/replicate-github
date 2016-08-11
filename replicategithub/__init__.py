import logging
import multiprocessing
import time

from replicategithub import webhook, mirror

class MirrorManager:
    """ Manage a collection of GitHub mirrors """
    def __init__(self, path, user, token, worker_count=2):
        self.collection = mirror.Collection(path, user, token)
        self.queue = multiprocessing.JoinableQueue()

        self.logger = logging.getLogger("MirrorManager")
        self.logger.debug("Starting {} workers".format(worker_count))

        for i in range(worker_count):
            mirror.Worker(self.collection, self.queue).start()

    def mirror_repo(self, repo_name):
        self.logger.debug("Adding job: mirror {}".format(repo_name))
        self.queue.put(("mirror", repo_name))

    def delete_mirror(self, repo_name):
        self.logger.debug("Adding job: delete {}".format(repo_name))
        self.queue.put(("delete", repo_name))

    def mirror_org(self, org):
        self.logger.debug("Adding job: mirror org {}".format(org))
        self.queue.put(("mirror_org", org))

    def sync_org(self, org):
        self.logger.debug("Adding sync job: {}".format(org))
        self.queue.put(("sync_org", org))

    def update_old_repos(self, maximum_age=24*60*60):
        before = time.time() - maximum_age
        for repo_name in self.collection.get_oldest_mirrors(before):
            self.logger.debug("Adding freshen job: update {}".format(repo_name))
            self.queue.put(("mirror", repo_name))

    def stop(self):
        self.logger.debug("Stopping all workers")
        self.queue.join()
        for child in multiprocessing.active_children():
            child.terminate()
        self.queue.close()
