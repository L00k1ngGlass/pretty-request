"""Turning an Exchange into the strings the GUI shows. Pure functions only."""

from __future__ import annotations

import json
import shlex
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl, urlsplit

import htmlreader
from exchange import Exchange
from htmlreader import Span

HEXDUMP_LIMIT = 4096
SKIPPED_CURL_HEADERS = ("host", "content-length", "connection")
HTML_MODES = ("Reader", "Source")


def human_size(size: int) -> str:
    if size < 1024:
        return "%d B" % size
    if size < 1024 * 1024:
        return "%.1f KB" % (size / 1024)
    return "%.1f MB" % (size / (1024 * 1024))


def human_time(ms: float) -> str:
    if ms < 1000:
        return "%d ms" % round(ms)
    return "%.2f s" % (ms / 1000)


def hexdump(data: bytes, limit: int = HEXDUMP_LIMIT) -> str:
    lines = []
    head = data[:limit]
    for offset in range(0, len(head), 16):
        chunk = head[offset : offset + 16]
        hex_part = " ".join("%02x" % byte for byte in chunk).ljust(47)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append("%08x  %s  |%s|" % (offset, hex_part, ascii_part))
    if len(data) > limit:
        lines.append("… %s more" % human_size(len(data) - limit))
    return "\n".join(lines)


# -- bodies ----------------------------------------------------------------


def is_html(exchange: Exchange) -> bool:
    """Whether the body should be offered in Reader/Source modes."""
    text = exchange.text()
    return text is not None and htmlreader.looks_like_html(exchange.content_type, text)


def render_body(exchange: Exchange, html_mode: str = "Reader") -> Tuple[str, str, List[Span]]:
    """Return ``(label, rendered body, colour spans)``.

    JSON and forms are pretty-printed, HTML is either read or syntax-coloured,
    and anything undecodable falls back to a hexdump.
    """
    if exchange.error is not None:
        return "no response", exchange.error, []
    if not exchange.body:
        return "no body", "(empty)", []

    size = human_size(len(exchange.body))
    text = exchange.text()
    if text is None:
        return "binary · %s" % size, hexdump(exchange.body), []

    if "json" in exchange.content_type or text.lstrip()[:1] in "{[":
        pretty = _try_json(text)
        if pretty is not None:
            return "JSON · %s" % size, pretty, []

    if exchange.content_type == "application/x-www-form-urlencoded":
        pretty = _try_form(text)
        if pretty is not None:
            fields = pretty.count("\n") + 1
            return "form · %d field%s" % (fields, "" if fields == 1 else "s"), pretty, []

    if is_html(exchange):
        if html_mode == "Source":
            return "HTML source · %s" % size, text, htmlreader.highlight(text)
        reader = htmlreader.to_text(text)
        words = len(reader.split())
        return "HTML reader view · %d words · %s" % (words, size), reader, []

    label = exchange.content_type or "text"
    if exchange.charset:
        label += " (%s)" % exchange.charset
    return "%s · %s" % (label, size), text, []


def _try_json(text: str) -> Optional[str]:
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return json.dumps(parsed, indent=2, ensure_ascii=False)


def _try_form(text: str) -> Optional[str]:
    pairs = parse_qsl(text, keep_blank_values=True)
    if not pairs:
        return None
    width = max(len(name) for name, _ in pairs)
    return "\n".join("%s  %s" % (name.ljust(width), value) for name, value in pairs)


# -- messages --------------------------------------------------------------


def render_request(exchange: Exchange) -> str:
    """The outgoing request, roughly as it went onto the wire."""
    parts = urlsplit(exchange.url)
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    lines = ["%s %s HTTP/1.1" % (exchange.method, target)]
    lines += ["%s: %s" % (name, value) for name, value in exchange.request_headers]
    if exchange.request_body:
        lines += ["", exchange.request_body.decode("utf-8", "replace")]
    return "\n".join(lines)


def render_response(exchange: Exchange) -> str:
    """The response, roughly as it came off the wire."""
    if exchange.error is not None:
        return "request failed: %s" % exchange.error
    lines = ["%s %s" % (exchange.http_version, exchange.status_line)]
    lines += ["%s: %s" % (name, value) for name, value in exchange.response_headers]
    lines.append("")
    text = exchange.text()
    lines.append(text if text is not None else hexdump(exchange.body))
    return "\n".join(lines)


def render_curl(exchange: Exchange) -> str:
    """A curl command that would repeat this request."""
    parts = ["curl -X %s %s" % (exchange.method, shlex.quote(exchange.url))]
    for name, value in exchange.request_headers:
        if name.lower() in SKIPPED_CURL_HEADERS:
            continue
        parts.append("-H %s" % shlex.quote("%s: %s" % (name, value)))
    if exchange.request_body:
        parts.append("--data-raw %s" % shlex.quote(exchange.request_body.decode("utf-8", "replace")))
    if exchange.redirected:
        parts.append("-L")
    return " \\\n  ".join(parts)


# -- tables ----------------------------------------------------------------


def summary_rows(exchange: Exchange) -> List[Tuple[str, str]]:
    """The property/value pairs shown on the Summary tab."""
    sent_at = "%s.%03d" % (exchange.at.strftime("%Y-%m-%d %H:%M:%S"), exchange.at.microsecond // 1000)
    rows = [
        ("Requested", exchange.url),
        ("Method", exchange.method),
        ("Sent at", sent_at),
        ("Elapsed", human_time(exchange.elapsed_ms)),
        ("Resolved IP", exchange.remote_ip or "—"),
    ]
    if exchange.error is not None:
        rows.append(("Error", exchange.error))
        return rows

    rows += [
        ("Status", exchange.status_line),
        ("HTTP version", exchange.http_version),
        ("Final URL", exchange.final_url if exchange.final_url != exchange.url else "same"),
        ("Redirects", str(len(exchange.redirects)) if exchange.redirects else "none"),
        ("Content type", exchange.header("Content-Type") or "—"),
        ("Body size", human_size(len(exchange.body))),
    ]
    if exchange.content_encoding:
        rows.append(
            ("Transferred", "%s %s" % (human_size(exchange.encoded_size), exchange.content_encoding))
        )
    rows += [
        ("Server", exchange.header("Server") or "—"),
        ("Cookies set", str(count_cookies(exchange))),
        ("Response headers", str(len(exchange.response_headers))),
    ]
    if is_html(exchange):
        rows += htmlreader.page_rows(exchange.text() or "")
    return rows


def link_rows(exchange: Exchange) -> List[Tuple[str, str]]:
    """Links found in an HTML body — empty for anything else."""
    if not is_html(exchange):
        return []
    return htmlreader.link_rows(exchange.text() or "")


def redirect_rows(exchange: Exchange) -> List[Tuple[str, str]]:
    return [(str(status), location) for status, location in exchange.redirects]


def count_cookies(exchange: Exchange) -> int:
    return sum(1 for name, _ in exchange.response_headers if name.lower() == "set-cookie")


def matches(exchange: Exchange, needle: str) -> bool:
    """Filter predicate for the history list."""
    needle = needle.strip().lower()
    if not needle:
        return True
    haystack = [exchange.method, exchange.url, exchange.status_line]
    haystack += ["%s: %s" % pair for pair in exchange.response_headers]
    return any(needle in item.lower() for item in haystack)
