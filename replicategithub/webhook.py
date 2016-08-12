import cgi
import hashlib
import http.server
import hmac
import logging
import json
import os
import threading

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def send(self, status, message, content=None):
        if content is None:
            content = message
        self.send_response(status, message)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

        self.wfile.write(content.encode('utf-8'))

    def do_POST(self):
        try:
            type = cgi.parse_header(self.headers['Content-Type'])[0]
            if type != 'application/json':
                self.send(415, "Payload must be application/json")
                return

            data = self.rfile.read(int(self.headers['Content-Length']))

            if not self.authenticate(data):
                self.send_header('WWW-Authenticate', 'X-Hub-Signature sha1')
                self.send(401, "Valid signature required")
                return

            event = self.headers['X-Github-Event']
            payload = json.loads(data.decode("utf-8", "strict"))

            self.do_webhook(event, payload)
        except:
            self.send(500, "Internal server error")
            raise

    def do_webhook(self, event, payload):
        if self.server.payload_log:
            self.server.payload_log.write(json.dumps({
                "event": event,
                "payload": payload
            }))

        if event == "ping":
            self.send(200, "pong")
        elif event == "repository":
            if payload["action"] == "deleted":
                self.server.manager.delete_mirror(
                    payload["repository"]["full_name"])
            else:
                # There will be a push event too.
                pass
            self.send(202, "Accepted")
        elif event == "push":
            self.server.manager.mirror_repo(
                payload["repository"]["full_name"])
            self.send(202, "Accepted")
        else:
            self.server.logger.error(
                "501 Event not implemented: {}".format(event))
            self.send(501, "Event not implemented")

    def authenticate(self, data):
        if self.server.secret is None:
            # No authentication configured
            return True

        signature = self.headers['X-Hub-Signature']
        if signature is None:
            return False

        secret_string = self.server.secret.encode("utf-8")
        digest = hmac.new(secret_string, data, hashlib.sha1).hexdigest()
        correct = "sha1={}".format(digest)

        return hmac.compare_digest(correct, signature)

class WebhookServer(http.server.HTTPServer):
    def __init__(self, address, secret, manager, payload_log):
        self.manager = manager
        self.secret = secret
        self.timer = None
        self.periodic_interval = 0
        self.logger = logging.getLogger("WebhookServer")
        self.payload_log = payload_log

        http.server.HTTPServer.__init__(self, address, WebhookHandler)

        self.logger.info("Webhook server listening on {}:{}"
            .format(address[0], address[1]))

    def start_periodic(self, periodic_interval=15*60, update_orgs=[],
            update_older_than=0):
        self.periodic_interval = periodic_interval
        self.update_orgs = update_orgs
        self.update_older_than = update_older_than
        self._schedule_periodic()

        self.logger.info("Configuration: run periodic tasks every {} seconds"
            .format(self.periodic_interval))
        self.logger.info("Configuration: keep orgs {} in sync"
            .format(self.update_orgs))
        self.logger.info("Configuration: update mirrors older than {} seconds"
            .format(self.update_older_than))

    def stop_periodic(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _schedule_periodic(self):
        if self.periodic_interval > 0:
            self.timer = threading.Timer(self.periodic_interval, self._periodic)
            self.timer.start()

    def _periodic(self):
        for org in self.update_orgs:
            self.logger.info("Periodic: synchronizing '{}'".format(org))
            self.manager.sync_org(org)

        if self.update_older_than:
            self.logger.info("Periodic: updating mirrors older than {} seconds"
                .format(self.update_older_than))
            self.manager.update_old_repos(maximum_age=self.update_older_than)

        self._schedule_periodic()


def serve(manager, secret=None, listen=("127.0.0.1", 8080),
        periodic_interval=15*60, update_orgs=[], update_older_than=0,
        payload_log=None):
    """
    Start an HTTP server to serve webhooks.

    This runs in the foreground.

    manager: a MirrorManager object.
    secret: the shared secret used to authenticate GitHub.
    address: (ip, port) to listen on.
    periodic_interval: how frequently to run periodic tasks.
    update_orgs: organizations to keep in sync.
    update_older_than: update mirrors that haven't been updated in this long.
    payload_log: file to log payloads to.
    """
    server = WebhookServer(listen, secret, manager, payload_log)
    if update_orgs or update_older_than:
        server.start_periodic(
            periodic_interval, update_orgs, update_older_than)
    try:
        server.serve_forever()
    finally:
        server.stop_periodic()
