import cgi
import hashlib
import http.server
import hmac
import json
import os
import sys

import replicategithub

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
        replicategithub.validate_repo_name(full_name)

        if payload["deleted"]:
            self.server.mirror.delete_repo(full_name)
        else:
            self.server.mirror.fetch_repo(full_name)

        self.send(200, "OK")

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
    def __init__(self, address, secret, mirror):
        self.mirror = mirror
        self.secret = secret
        http.server.HTTPServer.__init__(self, address, WebhookHandler)

def serve(mirror, secret=None, address=("127.0.0.1", 8080)):
    WebhookServer(address, secret, mirror).serve_forever()
