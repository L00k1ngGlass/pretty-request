"""The value object every other module talks in: one request/response pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

Header = Tuple[str, str]
Redirect = Tuple[int, str]  # (status, location)


@dataclass(frozen=True)
class Exchange:
    """One completed (or failed) HTTP exchange, frozen once it is done."""

    seq: int
    at: datetime
    method: str
    url: str  # what we asked for, after normalisation
    request_headers: List[Header] = field(default_factory=list)
    request_body: bytes = b""

    status: int = 0  # 0 means the request never got a response
    reason: str = ""
    http_version: str = ""
    final_url: str = ""
    response_headers: List[Header] = field(default_factory=list)
    body: bytes = b""  # already decompressed
    content_encoding: str = ""  # set only when we decompressed something
    encoded_size: int = 0  # bytes actually transferred, when compressed
    redirects: List[Redirect] = field(default_factory=list)
    remote_ip: str = ""
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    # -- helpers -----------------------------------------------------------

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def timestamp(self) -> str:
        return "%s.%03d" % (self.at.strftime("%H:%M:%S"), self.at.microsecond // 1000)

    @property
    def status_line(self) -> str:
        if self.error is not None:
            return "failed"
        return ("%d %s" % (self.status, self.reason)).strip()

    @property
    def content_type(self) -> str:
        """Media type without parameters, e.g. ``text/html``."""
        return _media_type(self.header("Content-Type"))

    @property
    def charset(self) -> str:
        return _charset(self.header("Content-Type"))

    @property
    def redirected(self) -> bool:
        return bool(self.redirects)

    def header(self, name: str) -> Optional[str]:
        """Case-insensitive response header lookup, as HTTP intends."""
        return _find(self.response_headers, name)

    def request_header(self, name: str) -> Optional[str]:
        return _find(self.request_headers, name)

    def text(self) -> Optional[str]:
        """The response body as text, or ``None`` when it is not decodable."""
        try:
            return self.body.decode(self.charset or "utf-8")
        except (UnicodeDecodeError, LookupError):
            try:
                return self.body.decode("utf-8")
            except UnicodeDecodeError:
                return None


def _find(headers: List[Header], name: str) -> Optional[str]:
    wanted = name.lower()
    for key, value in headers:
        if key.lower() == wanted:
            return value
    return None


def _media_type(content_type: Optional[str]) -> str:
    return (content_type or "").split(";")[0].strip()


def _charset(content_type: Optional[str]) -> str:
    for part in (content_type or "").split(";")[1:]:
        key, _, value = part.partition("=")
        if key.strip().lower() == "charset":
            return value.strip().strip('"').lower()
    return ""
