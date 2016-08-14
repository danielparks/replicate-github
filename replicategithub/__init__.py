import logging
import multiprocessing
import time

from replicategithub import webhook, mirror

class MirrorManager:
    """ Manage a collection of GitHub mirrors """
    def __init__(self, path, user, token, worker_count=2):
        self.logger = logging.getLogger("MirrorManager")
        self.logger.debug("Starting {} workers".format(worker_count))

        self.collection = mirror.Collection(path, user, token)
        self.pool = multiprocessing.Pool(processes=worker_count)
        self.current_jobs = 0
        self.busy_lock = multiprocessing.Lock()

    def _callable_to_str(self, callable):
        try:
            object = callable.__self__
        except AttributeError:
            object_string = ""
        else:
            object_string = object.__class__.__name__ + "."

        return object_string + callable.__name__

    def _run(self, callable, arguments, callback=None, error_callback=None):
        """
        Run a callable in another worker

        Keeps track of how many tasks are in the "queue" and managaes the busy
        lock. Blocking on the busy lock is essentially blocking until the
        queue is no longer busy.

        This is careful to handle tasks that generate other tasks correctly.
        It will not release the busy lock until all tasks and generated tasks
        are complete.
        """
        callable_string = self._callable_to_str(callable)

        def wrap_callback(_callback):
            def _wrapped(value):
                try:
                    if _callback:
                        _callback(value)
                finally:
                    # The callback might generate more jobs, so run it first to
                    # ensure we don't kill the pool prematurely.
                    self.logger.debug("pop {}{}".format(callable_string, arguments))
                    self.current_jobs -= 1
                    assert self.current_jobs >= 0
                    if self.current_jobs == 0:
                        self.logger.debug("releasing busy lock")
                        self.busy_lock.release()
            return _wrapped

        self.logger.debug("push {}{}".format(callable_string, arguments))

        assert self.current_jobs >= 0
        if self.current_jobs == 0:
            self.logger.debug("acquiring busy lock")
            if not self.busy_lock.acquire(block=False):
                raise Exception("current_jobs == 0 and busy_lock already held")

        self.current_jobs += 1
        self.pool.apply_async(callable, arguments,
            callback=wrap_callback(callback),
            error_callback=wrap_callback(error_callback))

    def mirror_repo(self, repo_name):
        self._run(self.collection.mirror_repo, (repo_name,))

    def delete_mirror(self, repo_name):
        self._run(self.collection.delete_mirror, (repo_name,))

    def mirror_org(self, org):
        def _callback_mirror_org(repos):
            mirrors = self.collection.get_mirror_names_set("{}/*".format(org))

            for repo_name in repos:
                self.mirror_repo(repo_name)
            for repo_name in mirrors - repos:
                self.delete_mirror(repo_name)

        self.logger.debug("mirror org {}".format(org))
        self._run(self.collection.get_org_repos_set, (org,),
            callback=_callback_mirror_org)

    def sync_org(self, org):
        def _callback_sync_org(repos):
            mirrors = self.collection.get_mirror_names_set("{}/*".format(org))

            for repo_name in repos - mirrors:
                self.mirror_repo(repo_name)
            for repo_name in mirrors - repos:
                self.delete_mirror(repo_name)

        self.logger.debug("sync org {}".format(org))
        self._run(self.collection.get_org_repos_set, (org,),
            callback=_callback_sync_org)

    def update_old_repos(self, maximum_age=24*60*60):
        before = time.time() - maximum_age
        for repo_name in self.collection.get_oldest_mirrors(before):
            self.mirror_repo(repo_name)

    def stop(self):
        """ Block until all outstanding work is done, then close the pool """
        self.logger.debug("Stopping: waiting for work queue to empty")

        with self.busy_lock:
            self.logger.debug("Closing and joining pool")
            self.pool.close()
            self.pool.join()
