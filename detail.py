"""Right pane: everything known about the selected exchange."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import theme
from exchange import Exchange
from formatting import (
    human_size,
    human_time,
    redirect_rows,
    render_body,
    render_curl,
    render_request,
    render_response,
    summary_rows,
)
from widgets import KeyValueTable, TextView

EMPTY_URL = "nothing sent yet"


class DetailView(ttk.Frame):
    def __init__(self, master, *, on_copy: Callable[[str], None]):
        super().__init__(master)
        self._on_copy = on_copy
        self._exchange: Optional[Exchange] = None
        self._body_label = tk.StringVar(value="")

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        self._badge = tk.Label(
            header,
            text="",
            background=theme.BG,
            foreground=theme.FG_MUTED,
            font=theme.fonts().mono_bold,
        )
        self._badge.pack(side="left")
        self._url = tk.Label(
            header,
            text=EMPTY_URL,
            background=theme.BG,
            foreground=theme.FG_MUTED,
            font=theme.fonts().mono,
            anchor="w",
        )
        self._url.pack(side="left", padx=(10, 0), fill="x", expand=True)
        self._timing = tk.Label(
            header, text="", background=theme.BG, foreground=theme.FG_MUTED, font=theme.fonts().mono_small
        )
        self._timing.pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(self._build_summary(notebook), text="Summary")
        notebook.add(self._build_response_headers(notebook), text="Response headers")
        notebook.add(self._build_request(notebook), text="Request")
        notebook.add(self._build_body(notebook), text="Body")
        notebook.add(self._build_raw(notebook), text="Raw")

        actions = ttk.Frame(self, padding=(0, 8, 0, 0))
        actions.pack(fill="x")
        ttk.Button(actions, text="Copy as cURL", command=self.copy_curl).pack(side="right")
        ttk.Button(actions, text="Copy response", command=self.copy_response).pack(side="right", padx=(0, 8))

    # -- panes -------------------------------------------------------------

    def _build_summary(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        self._summary = KeyValueTable(pane, "PROPERTY", "VALUE", key_width=190)
        self._summary.pack(fill="both", expand=True)
        ttk.Label(pane, text="REDIRECT CHAIN", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        self._redirects = KeyValueTable(pane, "STATUS", "LOCATION", key_width=90)
        self._redirects.pack(fill="both", expand=True)
        return pane

    def _build_response_headers(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        self._response_headers = KeyValueTable(pane, "HEADER", "VALUE", key_width=210)
        self._response_headers.pack(fill="both", expand=True)
        return pane

    def _build_request(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        self._request_headers = KeyValueTable(pane, "REQUEST HEADER", "VALUE", key_width=210)
        self._request_headers.pack(fill="both", expand=True)
        ttk.Label(pane, text="REQUEST AS SENT", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        self._request_raw = TextView(pane)
        self._request_raw.pack(fill="both", expand=True)
        return pane

    def _build_body(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        ttk.Label(pane, textvariable=self._body_label, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self._body = TextView(pane)
        self._body.pack(fill="both", expand=True)
        return pane

    def _build_raw(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        self._raw = TextView(pane)
        self._raw.pack(fill="both", expand=True)
        return pane

    # -- contents ----------------------------------------------------------

    def show(self, exchange: Exchange) -> None:
        self._exchange = exchange
        if exchange.ok:
            self._badge.configure(text=str(exchange.status), foreground=theme.status_color(exchange.status))
            self._timing.configure(
                text="%s · %s" % (human_time(exchange.elapsed_ms), human_size(len(exchange.body)))
            )
        else:
            self._badge.configure(text="ERR", foreground=theme.ERROR)
            self._timing.configure(text=human_time(exchange.elapsed_ms))
        self._url.configure(text="%s %s" % (exchange.method, exchange.url), foreground=theme.FG)

        self._summary.set_rows(summary_rows(exchange))
        self._redirects.set_rows(redirect_rows(exchange))
        self._response_headers.set_rows(exchange.response_headers)
        self._request_headers.set_rows(exchange.request_headers)
        self._request_raw.set_content(render_request(exchange))

        label, rendered = render_body(exchange)
        self._body_label.set(label)
        self._body.set_content(rendered)
        self._raw.set_content(render_response(exchange))

    def clear(self) -> None:
        self._exchange = None
        self._badge.configure(text="", foreground=theme.FG_MUTED)
        self._url.configure(text=EMPTY_URL, foreground=theme.FG_MUTED)
        self._timing.configure(text="")
        self._body_label.set("")
        for table in (self._summary, self._redirects, self._response_headers, self._request_headers):
            table.clear()
        for view in (self._body, self._raw, self._request_raw):
            view.set_content("")

    # -- actions -----------------------------------------------------------

    def copy_curl(self) -> None:
        if self._exchange is not None:
            self._on_copy(render_curl(self._exchange))

    def copy_response(self) -> None:
        if self._exchange is not None:
            self._on_copy(render_response(self._exchange))
