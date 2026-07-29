"""Request header profiles — what a real browser puts on the wire.

Servers vary their response on far more than the User-Agent: the `Accept` list
decides whether you get AVIF or JPEG, `Accept-Language` picks the translation,
the `Sec-Fetch-*` family tells the server whether this is a top-level navigation
or a script-initiated fetch, and Client Hints (`sec-ch-ua*`) identify Chromium
builds. Sending one lonely User-Agent string fools nobody and, more to the
point, gets you a different page than the one you are trying to inspect.

Header *order* is part of the fingerprint too, so each profile is an ordered
tuple, copied from the real thing.

Two honest limitations, both imposed by urllib (see README):
  * header names are title-cased in transit, so `sec-ch-ua` goes out as
    `Sec-Ch-Ua` — legal, since field names are case-insensitive, but not
    byte-identical to Chrome;
  * `Connection: close` is forced, because urllib does not pool connections.

And a deliberate one: browsers advertise `br` and `zstd`, which the standard
library cannot decompress, so every profile's `Accept-Encoding` is narrowed to
what we can actually decode. Ask for what you can read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

Header = Tuple[str, str]

# Browsers say "gzip, deflate, br, zstd"; we decode the first two. See module docstring.
ACCEPT_ENCODING = "gzip, deflate"
ACCEPT_LANGUAGE = "en-US,en;q=0.9"

# Bump these as browsers ship; the version appears in both the UA and the hints.
CHROME_VERSION = "137"
FIREFOX_VERSION = "140.0"
SAFARI_VERSION = "18.0"

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/%s.0.0.0 Safari/537.36" % CHROME_VERSION
)
FIREFOX_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:%s) Gecko/20100101 Firefox/%s"
    % (FIREFOX_VERSION, FIREFOX_VERSION)
)
SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/%s Safari/605.1.15" % SAFARI_VERSION
)
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/%s Mobile/15E148 Safari/604.1" % SAFARI_VERSION
)


@dataclass(frozen=True)
class Profile:
    """An ordered header set for a top-level navigation."""

    label: str
    navigation: Tuple[Header, ...]
    note: str = ""


# The Accept lines are verbatim from each browser: the q-values are how a server
# chooses between AVIF, WebP and JPEG, so trimming them changes what you get.
CHROME_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
)
FIREFOX_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
SAFARI_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

PROFILES: Dict[str, Profile] = {
    "Chrome (macOS)": Profile(
        label="Chrome (macOS)",
        note="Client Hints identify the Chromium build; Priority is the HTTP/2 hint Chrome sends.",
        navigation=(
            ("sec-ch-ua", '"Chromium";v="%s", "Not/A)Brand";v="24", "Google Chrome";v="%s"'
             % (CHROME_VERSION, CHROME_VERSION)),
            ("sec-ch-ua-mobile", "?0"),
            ("sec-ch-ua-platform", '"macOS"'),
            ("Upgrade-Insecure-Requests", "1"),
            ("User-Agent", CHROME_UA),
            ("Accept", CHROME_ACCEPT),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-User", "?1"),
            ("Sec-Fetch-Dest", "document"),
            ("Accept-Encoding", ACCEPT_ENCODING),
            ("Accept-Language", ACCEPT_LANGUAGE),
            ("Priority", "u=0, i"),
        ),
    ),
    "Firefox (macOS)": Profile(
        label="Firefox (macOS)",
        note="Firefox sends no Client Hints, and its Accept-Language q-value is 0.5, not 0.9.",
        navigation=(
            ("User-Agent", FIREFOX_UA),
            ("Accept", FIREFOX_ACCEPT),
            ("Accept-Language", "en-US,en;q=0.5"),
            ("Accept-Encoding", ACCEPT_ENCODING),
            ("Upgrade-Insecure-Requests", "1"),
            ("Sec-Fetch-Dest", "document"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-User", "?1"),
            ("Priority", "u=0, i"),
        ),
    ),
    "Safari (macOS)": Profile(
        label="Safari (macOS)",
        note="WebKit puts Accept first and User-Agent midway down; no Client Hints, no br for http.",
        navigation=(
            ("Accept", SAFARI_ACCEPT),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Dest", "document"),
            ("User-Agent", SAFARI_UA),
            ("Accept-Language", ACCEPT_LANGUAGE),
            ("Priority", "u=0, i"),
            ("Accept-Encoding", ACCEPT_ENCODING),
        ),
    ),
    "iPhone Safari": Profile(
        label="iPhone Safari",
        note="Same shape as desktop Safari; the UA is what triggers mobile layouts.",
        navigation=(
            ("Accept", SAFARI_ACCEPT),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Dest", "document"),
            ("User-Agent", IPHONE_UA),
            ("Accept-Language", ACCEPT_LANGUAGE),
            ("Priority", "u=0, i"),
            ("Accept-Encoding", ACCEPT_ENCODING),
        ),
    ),
    "curl": Profile(
        label="curl",
        note="What curl actually sends: three headers, no more.",
        navigation=(
            ("User-Agent", "curl/8.7.1"),
            ("Accept", "*/*"),
            ("Accept-Encoding", ACCEPT_ENCODING),
        ),
    ),
    "pretty-request": Profile(
        label="pretty-request",
        note="Honest identification — say who you are unless you need the browser's view.",
        navigation=(
            ("User-Agent", "pretty-request/0.1"),
            ("Accept", "*/*"),
            ("Accept-Encoding", ACCEPT_ENCODING),
        ),
    ),
}

DEFAULT_PROFILE = "Chrome (macOS)"
NAVIGATION_METHODS = ("GET", "HEAD")

# Swapped in when the request is not a top-level navigation — i.e. what the same
# browser sends from fetch()/XHR. Order within the header list is preserved.
_FETCH_SWAPS = {
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept": "*/*",
    "Priority": "u=1, i",
}
# Only a navigation carries these.
_NAVIGATION_ONLY = ("Sec-Fetch-User", "Upgrade-Insecure-Requests")


def names() -> List[str]:
    """Profile names, in the order they should appear in the picker."""
    return list(PROFILES)


def note(profile: str) -> str:
    return PROFILES.get(profile, PROFILES[DEFAULT_PROFILE]).note


def headers_for(
    profile: str,
    *,
    url: str,
    method: str = "GET",
    content_type: str = "",
    body: Optional[bytes] = None,
    referer: str = "",
) -> List[Header]:
    """Build the ordered header list for one request.

    Host comes first, as it does on the wire. A request that carries a body is
    treated as a script-initiated fetch rather than a navigation, which is what
    a browser would really be doing at that point.
    """
    chosen = PROFILES.get(profile) or PROFILES[DEFAULT_PROFILE]
    parts = urlsplit(url)
    navigating = method.upper() in NAVIGATION_METHODS and body is None

    headers: List[Header] = [("Host", parts.netloc)]
    for name, value in chosen.navigation:
        if navigating:
            headers.append((name, value))
            continue
        if name in _NAVIGATION_ONLY:
            continue
        if name == "Sec-Fetch-Site":
            # A cross-origin fetch announces its own page's origin first.
            headers.append(("Origin", "%s://%s" % (parts.scheme, parts.netloc)))
        headers.append((name, _FETCH_SWAPS.get(name, value)))

    if referer:
        headers.append(("Referer", referer))
    if body is not None:
        headers.append(("Content-Type", content_type or "application/octet-stream"))
        headers.append(("Content-Length", str(len(body))))
    return headers
