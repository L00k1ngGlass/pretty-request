"""pretty-request — a lightweight tkinter inspector for HTTP requests.

Type an address, hit Send, and see the whole exchange laid out: status, timing,
redirect chain, request and response headers, and a pretty-printed body.
"""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

import fetcher
import profiles
import theme
from detail import DetailView
from exchange import Exchange
from formatting import human_size, human_time
from history import History
from url_bar import UrlBar

POLL_INTERVAL_MS = 60
FLASH_MS = 1400


class App(tk.Tk):
    def __init__(
        self,
        url: str = "",
        timeout: float = fetcher.DEFAULT_TIMEOUT,
        profile: str = profiles.DEFAULT_PROFILE,
    ):
        super().__init__()
        self.title("pretty-request")
        self.geometry("1180x760")
        self.minsize(900, 560)
        self.configure(background=theme.BG)
        theme.apply(self)

        self._timeout = timeout
        self._seq = 0
        self._inflight = 0
        # Worker threads put finished exchanges here; the Tk loop drains them.
        self._inbox: "queue.Queue[Exchange]" = queue.Queue()

        self.url_bar = UrlBar(self, on_send=self.send, on_clear=self.clear, profile=profile)
        self.url_bar.pack(fill="x")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        self.history = History(panes, on_select=self.detail_show)
        self.detail = DetailView(panes, on_copy=self.copy)
        panes.add(self.history, weight=2)
        panes.add(self.detail, weight=3)

        self.bind("<Command-l>", lambda _event: self.url_bar.focus_url())
        self.bind("<Control-l>", lambda _event: self.url_bar.focus_url())
        self.bind("<Command-k>", lambda _event: self.clear())

        if url:
            self.url_bar.set_url(url)
        self.after(POLL_INTERVAL_MS, self._drain)
        self.after(100, self.url_bar.focus_url)
        if url:
            self.after(200, self.send)

    # -- sending -----------------------------------------------------------

    def send(self) -> None:
        """Kick off a request on a worker thread; the GUI stays responsive."""
        try:
            url = fetcher.normalize_url(self.url_bar.url())
        except fetcher.InvalidURL as error:
            self.url_bar.set_status(str(error), theme.ERROR)
            return

        self._seq += 1
        self._inflight += 1
        self.url_bar.set_busy(True)
        self.url_bar.set_status("sending %s %s…" % (self.url_bar.method(), url), theme.ACCENT)

        thread = threading.Thread(
            target=self._work,
            args=(
                self._seq,
                self.url_bar.method(),
                url,
                self.url_bar.body(),
                self.url_bar.content_type(),
                self.url_bar.profile(),
            ),
            name="fetch-%d" % self._seq,
            daemon=True,
        )
        thread.start()

    def _work(
        self, seq: int, method: str, url: str, body: Optional[bytes], content_type: str, profile: str
    ) -> None:
        self._inbox.put(
            fetcher.fetch(
                method,
                url,
                seq=seq,
                body=body,
                content_type=content_type,
                timeout=self._timeout,
                profile=profile,
            )
        )

    # -- results -----------------------------------------------------------

    def _drain(self) -> None:
        newest = None
        while True:
            try:
                exchange = self._inbox.get_nowait()
            except queue.Empty:
                break
            self._inflight -= 1
            if self.history.add(exchange):
                newest = exchange
        if newest is not None:
            self.history.select(newest)
            self._report(newest)
        if self._inflight <= 0:
            self.url_bar.set_busy(False)
        self.after(POLL_INTERVAL_MS, self._drain)

    def _report(self, exchange: Exchange) -> None:
        if not exchange.ok:
            self.url_bar.set_status(exchange.error or "request failed", theme.ERROR)
            return
        summary = "%s · %s · %s" % (
            exchange.status_line,
            human_time(exchange.elapsed_ms),
            human_size(len(exchange.body)),
        )
        self.url_bar.set_status(summary, theme.status_color(exchange.status))

    def detail_show(self, exchange: Exchange) -> None:
        self.detail.show(exchange)

    def clear(self) -> None:
        self.history.clear()
        self.detail.clear()
        self.url_bar.set_status("ready", theme.FG_MUTED)

    def copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        previous = self.url_bar.status
        self.url_bar.set_status("copied to clipboard", theme.ACCENT)
        self.after(FLASH_MS, lambda: self.url_bar.set_status(*previous))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?", default="", help="address to load on startup")
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=fetcher.DEFAULT_TIMEOUT,
        help="request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--profile",
        choices=profiles.names(),
        default=profiles.DEFAULT_PROFILE,
        help="header profile to send as (default: %(default)s)",
    )
    args = parser.parse_args()
    App(url=args.url, timeout=args.timeout, profile=args.profile).mainloop()


if __name__ == "__main__":
    main()
