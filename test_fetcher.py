"""Tests for the fetcher, driven against a throwaway local server."""

from __future__ import annotations

import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fetcher import InvalidURL, fetch, normalize_url


class _TargetHandler(BaseHTTPRequestHandler):
    """A tiny site to point the fetcher at: JSON, redirects and errors."""

    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/json":
            self._send(200, b'{"hello":"world"}', "application/json")
        elif self.path == "/hop":
            self._redirect("/hop2")
        elif self.path == "/hop2":
            self._redirect("/json")
        elif self.path == "/missing":
            self._send(404, b"nope", "text/plain")
        elif self.path == "/boom":
            self._send(500, b"kaboom", "text/plain")
        else:
            self._send(200, b"<h1>hi</h1>", "text/html; charset=utf-8")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        echo = {
            "body": self.rfile.read(length).decode(),
            "content_type": self.headers.get("Content-Type"),
            "user_agent": self.headers.get("User-Agent"),
        }
        self._send(201, json.dumps(echo).encode(), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", "session=abc; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        """Keep the test output clean."""


class NormalizeUrlTest(unittest.TestCase):
    def test_bare_hostname_gets_https(self):
        self.assertEqual(normalize_url("example.com"), "https://example.com/")
        self.assertEqual(normalize_url("  example.com/a?b=1 "), "https://example.com/a?b=1")

    def test_existing_scheme_is_kept(self):
        self.assertEqual(normalize_url("http://example.com"), "http://example.com/")

    def test_local_addresses_default_to_http(self):
        self.assertEqual(normalize_url("localhost:8000"), "http://localhost:8000/")
        self.assertEqual(normalize_url("127.0.0.1:3000/x"), "http://127.0.0.1:3000/x")
        self.assertEqual(normalize_url("box.local"), "http://box.local/")

    def test_fragments_are_dropped(self):
        self.assertEqual(normalize_url("example.com/a#top"), "https://example.com/a")

    def test_rejects_junk(self):
        for bad in ("", "   ", "ftp://example.com", "https://"):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidURL):
                    normalize_url(bad)


class FetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_json_response_is_captured_whole(self):
        exchange = fetch("GET", self.base + "/json")
        self.assertTrue(exchange.ok)
        self.assertEqual(exchange.status, 200)
        self.assertEqual(exchange.reason, "OK")
        self.assertEqual(exchange.body, b'{"hello":"world"}')
        self.assertEqual(exchange.content_type, "application/json")
        self.assertEqual(exchange.http_version, "HTTP/1.1")
        self.assertEqual(exchange.remote_ip, "127.0.0.1")
        self.assertGreater(exchange.elapsed_ms, 0)
        self.assertEqual(exchange.header("Set-Cookie"), "session=abc; Path=/")

    def test_request_headers_are_recorded(self):
        exchange = fetch("GET", self.base + "/json")
        self.assertEqual(exchange.request_header("Host"), exchange.url.split("//")[1].split("/")[0])
        self.assertEqual(exchange.request_header("User-Agent"), "pretty-request/0.1")
        self.assertEqual(exchange.request_header("Accept-Encoding"), "identity")

    def test_redirect_chain_is_followed_and_recorded(self):
        exchange = fetch("GET", self.base + "/hop")
        self.assertTrue(exchange.redirected)
        self.assertEqual([status for status, _ in exchange.redirects], [302, 302])
        self.assertTrue(exchange.final_url.endswith("/json"))
        self.assertEqual(exchange.status, 200)

    def test_error_statuses_are_normal_exchanges(self):
        for path, status in (("/missing", 404), ("/boom", 500)):
            with self.subTest(path=path):
                exchange = fetch("GET", self.base + path)
                self.assertTrue(exchange.ok)  # a response arrived; it just wasn't a 2xx
                self.assertEqual(exchange.status, status)
                self.assertTrue(exchange.body)

    def test_post_sends_body_and_content_type(self):
        exchange = fetch(
            "POST", self.base + "/echo", body=b'{"a":1}', content_type="application/json"
        )
        self.assertEqual(exchange.status, 201)
        echoed = json.loads(exchange.body)
        self.assertEqual(echoed["body"], '{"a":1}')
        self.assertEqual(echoed["content_type"], "application/json")
        self.assertEqual(exchange.request_header("Content-Length"), "7")

    def test_body_is_dropped_for_methods_that_cannot_carry_one(self):
        exchange = fetch("GET", self.base + "/json", body=b"ignored")
        self.assertEqual(exchange.request_body, b"")
        self.assertIsNone(exchange.request_header("Content-Type"))

    def test_connection_failure_becomes_a_failed_exchange(self):
        with socket.socket() as sock:  # bind a port, then let it close: nothing listens
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        exchange = fetch("GET", "http://127.0.0.1:%d/" % port)
        self.assertFalse(exchange.ok)
        self.assertIn("refused", exchange.error.lower())
        self.assertEqual(exchange.status, 0)

    def test_unresolvable_host_is_reported_clearly(self):
        exchange = fetch("GET", "http://nonexistent.invalid/")
        self.assertFalse(exchange.ok)
        self.assertEqual(exchange.error, "could not resolve host")


if __name__ == "__main__":
    unittest.main()
