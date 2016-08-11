import cgi
import hashlib
import http.server
import hmac
import json
import os

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
        if event == "ping":
            self.send(200, "pong")
            return

        full_name = payload["repository"]["full_name"]

        if payload["deleted"]:
            self.server.manager.delete_mirror(full_name)
        else:
            self.server.manager.mirror_repo(full_name)

        self.send(202, "Accepted")

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
    def __init__(self, address, secret, manager):
        self.manager = manager
        self.secret = secret
        http.server.HTTPServer.__init__(self, address, WebhookHandler)

def serve(manager, secret=None, address=("127.0.0.1", 8080)):
    """
    Start an HTTP server on address to server webhooks

    This runs in the foreground.

    manager: a MirrorManager object.
    secret: the shared secret used to authenticate GitHub.
    address: (ip, port) to listen on.
    """
    WebhookServer(address, secret, manager).serve_forever()
