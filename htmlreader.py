"""Making HTML readable: a text extractor, page metadata, and source colouring.

This is deliberately not a rendering engine — no layout, no CSS. It answers the
two questions you actually have when inspecting a page: what does it say, and
what is in the markup.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Tuple
from urllib.parse import urljoin

# Content in these never belongs in a reader view.
SKIPPED = {"script", "style", "noscript", "template", "svg", "head"}
# Tags that end the current line of prose.
BLOCKS = {
    "address", "article", "aside", "blockquote", "br", "div", "dd", "dl", "dt",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
    "td", "th", "tr", "ul",
}
HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
COUNTED = ("a", "img", "script", "link", "form", "input", "iframe")

Span = Tuple[str, int, int]  # (kind, start offset, end offset)

_TAG = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<[^>]*>", re.DOTALL)
_TAG_NAME = re.compile(r"</?\s*([A-Za-z][-\w:]*)")
_ATTR = re.compile(r"([-\w:]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'>]+)")
_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]+")


class _Reader(HTMLParser):
    """Collects visible text, page metadata and element counts in one pass."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: List[str] = []
        self.meta: Dict[str, str] = {}
        self.counts: Dict[str, int] = dict.fromkeys(COUNTED, 0)
        self.headings: List[Tuple[str, str]] = []
        self.links: List[Tuple[str, str]] = []
        self._skip_depth = 0
        self._in_title = False
        self._heading = ""
        self._pending_href = ""
        self._buffer: List[str] = []

    # -- tags --------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in self.counts:
            self.counts[tag] += 1
        if tag == "html" and attributes.get("lang"):
            self.meta.setdefault("lang", attributes["lang"])
        elif tag == "meta":
            self._read_meta(attributes)
        elif tag == "base" and attributes.get("href"):
            # A <base> tag rebases every relative URL on the page.
            self.meta.setdefault("base", attributes["href"])
        elif tag == "a" and attributes.get("href"):
            self._buffer = []
            self._pending_href = attributes["href"]
        elif tag == "img" and attributes.get("alt"):
            self.chunks.append("[image: %s]" % attributes["alt"])

        if tag in SKIPPED:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in HEADINGS:
            self._heading = tag
            self.chunks.append("\n%s " % HEADINGS[tag])
        elif tag in BLOCKS:
            self.chunks.append("\n")
        if tag == "li":
            self.chunks.append("• ")

    def handle_endtag(self, tag):
        if tag in SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in HEADINGS:
            self._heading = ""
            self.chunks.append("\n")
        elif tag in BLOCKS:
            self.chunks.append("\n")
        if tag == "a" and self._pending_href:
            text = _collapse("".join(self._buffer))
            self.links.append((text or "(no text)", self._pending_href))
            self._pending_href = ""
            self._buffer = []

    def handle_data(self, data):
        if self._in_title:
            self.meta.setdefault("title", _collapse(data))
            return
        if self._skip_depth:
            return
        if self._pending_href:
            self._buffer.append(data)
        if self._heading:
            self.headings.append((self._heading, _collapse(data)))
        self.chunks.append(data)

    # -- helpers -----------------------------------------------------------

    def _read_meta(self, attributes: Dict[str, str]) -> None:
        if attributes.get("charset"):
            self.meta.setdefault("charset", attributes["charset"])
        key = (attributes.get("name") or attributes.get("property") or "").lower()
        content = attributes.get("content", "")
        if key in ("description", "og:description") and content:
            self.meta.setdefault("description", _collapse(content))
        elif key in ("og:title", "twitter:title") and content:
            self.meta.setdefault("title", _collapse(content))
        elif key == "generator" and content:
            self.meta.setdefault("generator", _collapse(content))

    def text(self) -> str:
        joined = _SPACES.sub(" ", "".join(self.chunks))
        lines = [line.strip() for line in joined.splitlines()]
        return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _parse(source: str) -> _Reader:
    reader = _Reader()
    try:
        reader.feed(source)
        reader.close()
    except AssertionError:  # malformed markup; keep whatever we got
        pass
    return reader


# -- public API ------------------------------------------------------------


def looks_like_html(content_type: str, text: str) -> bool:
    if "html" in content_type:
        return True
    if content_type and "xml" not in content_type:
        return False
    head = text.lstrip()[:512].lower()
    return head.startswith("<!doctype html") or "<html" in head


def to_text(source: str) -> str:
    """The page as readable prose, with headings marked and scripts dropped."""
    return _parse(source).text()


def page_rows(source: str) -> List[Tuple[str, str]]:
    """Metadata rows for the Summary tab — title, description, element counts."""
    reader = _parse(source)
    rows = []
    for label, key in (("Page title", "title"), ("Description", "description"),
                       ("Language", "lang"), ("Meta charset", "charset"), ("Generator", "generator")):
        if reader.meta.get(key):
            rows.append((label, _clip(reader.meta[key])))
    counts = reader.counts
    rows.append(("Links", str(counts["a"])))
    rows.append(("Images", str(counts["img"])))
    rows.append(("Scripts", str(counts["script"])))
    rows.append(("Stylesheets / links", str(counts["link"])))
    if counts["form"] or counts["input"]:
        rows.append(("Forms / inputs", "%d / %d" % (counts["form"], counts["input"])))
    if counts["iframe"]:
        rows.append(("Iframes", str(counts["iframe"])))
    if reader.headings:
        rows.append(("Headings", ", ".join(text for _, text in reader.headings[:6]) or "—"))
    return rows


def link_rows(source: str, base_url: str = "", limit: int = 200) -> List[Tuple[str, str]]:
    """``(link text, href)`` pairs in document order, resolved against the page.

    Relative hrefs are joined onto ``base_url`` — or onto the page's own
    ``<base href>`` when it has one — so a copied link is usable on its own.
    """
    reader = _parse(source)
    base = urljoin(base_url, reader.meta.get("base", "")) if base_url else reader.meta.get("base", "")
    return [(text, urljoin(base, href) if base else href) for text, href in reader.links[:limit]]


def highlight(source: str, limit: int = 200_000) -> List[Span]:
    """Spans for colouring the markup: comments, tags, attributes, values."""
    spans: List[Span] = []
    for match in _TAG.finditer(source[:limit]):
        start, end = match.span()
        chunk = match.group()
        if chunk.startswith("<!--"):
            spans.append(("comment", start, end))
            continue
        if chunk.startswith("<!"):
            spans.append(("doctype", start, end))
            continue

        spans.append(("punct", start, end))
        name = _TAG_NAME.match(chunk)
        if name:
            spans.append(("tag", start + name.start(1), start + name.end(1)))
        for attr in _ATTR.finditer(chunk):
            spans.append(("attr", start + attr.start(1), start + attr.end(1)))
            spans.append(("value", start + attr.start(2), start + attr.end(2)))
    return spans


def _clip(text: str, width: int = 160) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"
