"""Performing the request. Standard library only — urllib does the talking."""

from __future__ import annotations

import gzip
import socket
import ssl
import time
import zlib
import urllib.error
import urllib.request
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import profiles
from exchange import Exchange, Redirect

METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")
DEFAULT_TIMEOUT = 15
DEFAULT_SCHEME = "https"


class InvalidURL(ValueError):
    """Raised when what the user typed cannot be turned into a URL."""


LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def normalize_url(text: str) -> str:
    """Turn what someone typed into a URL. ``example.com`` → ``https://example.com/``."""
    text = text.strip()
    if not text:
        raise InvalidURL("enter a website address")
    if "//" not in text.split("?", 1)[0][:8]:
        text = "%s://%s" % (_implied_scheme(text), text.lstrip("/"))

    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        raise InvalidURL("unsupported scheme %r — use http or https" % parts.scheme)
    if not parts.netloc:
        raise InvalidURL("that address has no host")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def _implied_scheme(text: str) -> str:
    """https, except for the places that almost never speak it."""
    host = text.split("/", 1)[0].split("?", 1)[0]
    hostname, _, port = host.rpartition(":")
    if not hostname:  # no colon at all
        hostname, port = host, ""
    if hostname.lower() in LOCAL_HOSTS or hostname.lower().endswith(".local"):
        return "http"
    if port.isdigit() and port not in ("443", "8443"):
        return "http"
    return DEFAULT_SCHEME


class _RedirectTracker(urllib.request.HTTPRedirectHandler):
    """A redirect handler that remembers every hop it followed."""

    def __init__(self):
        self.chain: List[Redirect] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(
    method: str,
    url: str,
    *,
    seq: int = 1,
    body: Optional[bytes] = None,
    content_type: str = "",
    timeout: float = DEFAULT_TIMEOUT,
    profile: str = profiles.DEFAULT_PROFILE,
) -> Exchange:
    """Send one request and return the resulting :class:`Exchange`.

    Never raises for network problems: failures come back as an exchange with
    ``error`` set, so the GUI can list them alongside the successes.
    """
    method = method.upper()
    url = normalize_url(url)
    body = body if method in BODY_METHODS else None
    wanted = profiles.headers_for(
        profile, url=url, method=method, content_type=content_type, body=body
    )
    headers = _wire_headers(wanted)

    request = urllib.request.Request(url, data=body, method=method)
    for name, value in wanted:
        if name.lower() != "host":  # urllib derives Host from the URL itself
            request.add_header(name, value)

    tracker = _RedirectTracker()
    opener = urllib.request.build_opener(tracker)
    started_at = datetime.now()
    clock = time.perf_counter()

    def build(**overrides) -> Exchange:
        defaults = dict(
            seq=seq,
            at=started_at,
            method=method,
            url=url,
            request_headers=headers,
            request_body=body or b"",
            profile=profile,
            redirects=tracker.chain,
            remote_ip=_resolve(url),
            elapsed_ms=(time.perf_counter() - clock) * 1000,
        )
        defaults.update(overrides)
        return Exchange(**defaults)

    try:
        with opener.open(request, timeout=timeout) as response:
            return build(**_from_response(response))
    except urllib.error.HTTPError as error:
        # A 4xx/5xx is a perfectly good response; urllib just raises it.
        with error:
            return build(**_from_response(error))
    except (urllib.error.URLError, ssl.SSLError, socket.timeout, OSError) as error:
        return build(error=_describe(error))


def _from_response(response) -> dict:
    raw = response.read()
    encoding = (response.headers.get("Content-Encoding") or "").strip().lower()
    body = _decompress(raw, encoding)
    return dict(
        status=response.status,
        reason=response.reason or "",
        http_version=_http_version(response),
        final_url=response.geturl(),
        response_headers=list(response.headers.items()),
        body=body,
        content_encoding=encoding if body is not raw else "",
        encoded_size=len(raw) if body is not raw else 0,
    )


def _decompress(raw: bytes, encoding: str) -> bytes:
    """Undo Content-Encoding. CDNs compress even when asked for identity.

    Returns ``raw`` itself when there is nothing to do or the payload will not
    decompress — the hexdump then shows exactly what arrived.
    """
    gzipped = encoding == "gzip" or (not encoding and raw[:2] == b"\x1f\x8b")
    try:
        if gzipped:
            return gzip.decompress(raw)
        if encoding in ("deflate", "zlib"):
            try:
                return zlib.decompress(raw)
            except zlib.error:  # raw deflate stream, no zlib wrapper
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except (OSError, EOFError, zlib.error):
        return raw
    return raw


def _wire_headers(headers: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """What urllib will really send, so the Request tab does not lie.

    ``do_open`` title-cases every field name (``sec-ch-ua`` → ``Sec-Ch-Ua``;
    legal, since field names are case-insensitive) and appends ``Connection:
    close``, because it does not pool connections. Both are visible to a server
    doing HTTP/1.1 fingerprinting, so we record them rather than our intent.
    """
    return [(name.title(), value) for name, value in headers] + [("Connection", "close")]


def _http_version(response) -> str:
    return {10: "HTTP/1.0", 11: "HTTP/1.1"}.get(getattr(response, "version", None), "HTTP/1.1")


def _resolve(url: str) -> str:
    """Best-effort IP for the host — informational, so failures are silent."""
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        return socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)[0][4][0]
    except (socket.gaierror, UnicodeError, IndexError, TypeError):
        return ""


def _describe(error: Exception) -> str:
    reason = getattr(error, "reason", error)
    if isinstance(reason, socket.timeout):
        return "timed out"
    if isinstance(reason, socket.gaierror):
        return "could not resolve host"
    if isinstance(reason, ssl.SSLError):
        return "TLS error: %s" % (reason.reason or reason)
    return str(reason) or error.__class__.__name__
