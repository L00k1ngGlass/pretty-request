"""Tests for the rendering helpers — no Tk and no network involved."""

from __future__ import annotations

import unittest
from datetime import datetime

from exchange import Exchange
from formatting import (
    human_size,
    human_time,
    matches,
    redirect_rows,
    render_body,
    render_curl,
    render_request,
    render_response,
    summary_rows,
)


def make_exchange(**overrides) -> Exchange:
    defaults = dict(
        seq=1,
        at=datetime(2026, 7, 28, 21, 55, 3, 123000),
        method="GET",
        url="https://example.com/api/users?page=2",
        request_headers=[("Host", "example.com"), ("User-Agent", "pretty-request/0.1")],
        status=200,
        reason="OK",
        http_version="HTTP/1.1",
        final_url="https://example.com/api/users?page=2",
        response_headers=[("Content-Type", "application/json"), ("Server", "nginx")],
        body=b'{"page":2}',
        remote_ip="93.184.216.34",
        elapsed_ms=142.4,
    )
    defaults.update(overrides)
    return Exchange(**defaults)


class HumanUnitsTest(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(3 * 1024 * 1024), "3.0 MB")

    def test_times(self):
        self.assertEqual(human_time(142.4), "142 ms")
        self.assertEqual(human_time(2500), "2.50 s")


class ExchangeTest(unittest.TestCase):
    def test_header_lookup_is_case_insensitive(self):
        self.assertEqual(make_exchange().header("content-type"), "application/json")
        self.assertIsNone(make_exchange().header("X-Missing"))

    def test_content_type_and_charset(self):
        exchange = make_exchange(response_headers=[("Content-Type", 'text/html; charset="ISO-8859-1"')])
        self.assertEqual(exchange.content_type, "text/html")
        self.assertEqual(exchange.charset, "iso-8859-1")

    def test_body_decoded_with_declared_charset(self):
        exchange = make_exchange(
            response_headers=[("Content-Type", "text/plain; charset=latin-1")],
            body="café".encode("latin-1"),
        )
        self.assertEqual(exchange.text(), "café")

    def test_status_line_and_ok(self):
        self.assertEqual(make_exchange().status_line, "200 OK")
        failed = make_exchange(status=0, reason="", error="could not resolve host")
        self.assertFalse(failed.ok)
        self.assertEqual(failed.status_line, "failed")


class RenderBodyTest(unittest.TestCase):
    def test_json_is_pretty_printed(self):
        label, rendered = render_body(make_exchange())
        self.assertTrue(label.startswith("JSON"))
        self.assertEqual(rendered, '{\n  "page": 2\n}')

    def test_html_is_shown_as_text(self):
        exchange = make_exchange(
            response_headers=[("Content-Type", "text/html; charset=utf-8")], body=b"<h1>hi</h1>"
        )
        label, rendered = render_body(exchange)
        self.assertEqual(label, "text/html (utf-8) · 11 B")
        self.assertEqual(rendered, "<h1>hi</h1>")

    def test_empty_and_binary_and_failed(self):
        self.assertEqual(render_body(make_exchange(body=b""))[1], "(empty)")
        self.assertIn("00000000  00 01 ff", render_body(make_exchange(body=b"\x00\x01\xff"))[1])
        self.assertEqual(render_body(make_exchange(error="timed out"))[1], "timed out")


class RenderMessagesTest(unittest.TestCase):
    def test_request_message(self):
        lines = render_request(make_exchange()).splitlines()
        self.assertEqual(lines[0], "GET /api/users?page=2 HTTP/1.1")
        self.assertEqual(lines[1], "Host: example.com")

    def test_request_message_includes_body(self):
        exchange = make_exchange(method="POST", request_body=b'{"a":1}')
        self.assertEqual(render_request(exchange).splitlines()[-1], '{"a":1}')

    def test_response_message(self):
        lines = render_response(make_exchange()).splitlines()
        self.assertEqual(lines[0], "HTTP/1.1 200 OK")
        self.assertEqual(lines[1], "Content-Type: application/json")
        self.assertEqual(lines[4], '{"page":2}')

    def test_response_message_for_failure(self):
        self.assertEqual(render_response(make_exchange(error="timed out")), "request failed: timed out")


class RenderCurlTest(unittest.TestCase):
    def test_reproduces_the_request(self):
        command = render_curl(make_exchange())
        self.assertIn("curl -X GET 'https://example.com/api/users?page=2'", command)
        self.assertIn("-H 'User-Agent: pretty-request/0.1'", command)
        self.assertNotIn("-H 'Host:", command)

    def test_body_and_redirect_flags(self):
        exchange = make_exchange(
            method="POST", request_body=b'{"a":1}', redirects=[(301, "https://example.com/new")]
        )
        command = render_curl(exchange)
        self.assertIn("--data-raw '{\"a\":1}'", command)
        self.assertIn("-L", command)


class SummaryTest(unittest.TestCase):
    def test_rows_cover_the_essentials(self):
        rows = dict(summary_rows(make_exchange()))
        self.assertEqual(rows["Status"], "200 OK")
        self.assertEqual(rows["Elapsed"], "142 ms")
        self.assertEqual(rows["Resolved IP"], "93.184.216.34")
        self.assertEqual(rows["Final URL"], "same")
        self.assertEqual(rows["Redirects"], "none")
        self.assertEqual(rows["Server"], "nginx")

    def test_failed_exchange_reports_the_error_and_stops(self):
        rows = dict(summary_rows(make_exchange(status=0, error="could not resolve host")))
        self.assertEqual(rows["Error"], "could not resolve host")
        self.assertNotIn("Status", rows)

    def test_redirect_rows(self):
        exchange = make_exchange(redirects=[(301, "https://example.com/new"), (302, "https://cdn/x")])
        self.assertEqual(redirect_rows(exchange)[0], ("301", "https://example.com/new"))
        self.assertEqual(len(redirect_rows(make_exchange())), 0)


class MatchesTest(unittest.TestCase):
    def test_blank_filter_matches_everything(self):
        self.assertTrue(matches(make_exchange(), "  "))

    def test_matches_status_method_url_and_headers(self):
        exchange = make_exchange()
        self.assertTrue(matches(exchange, "200"))
        self.assertTrue(matches(exchange, "get"))
        self.assertTrue(matches(exchange, "example.com"))
        self.assertTrue(matches(exchange, "nginx"))
        self.assertFalse(matches(exchange, "404"))


if __name__ == "__main__":
    unittest.main()
