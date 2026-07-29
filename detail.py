"""Right pane: everything known about the selected exchange."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import theme
from exchange import Exchange
from formatting import (
    HTML_MODES,
    human_size,
    human_time,
    is_html,
    link_rows,
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
        self._html_mode = tk.StringVar(value=HTML_MODES[0])

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

        self._notebook = notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(self._build_summary(notebook), text="Summary")
        notebook.add(self._build_response_headers(notebook), text="Response headers")
        notebook.add(self._build_request(notebook), text="Request")
        notebook.add(self._build_body(notebook), text="Body")
        self._links_pane = self._build_links(notebook)
        notebook.add(self._links_pane, text="Links")
        notebook.hide(self._links_pane)  # only shown for HTML bodies
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

        controls = ttk.Frame(pane)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Label(controls, textvariable=self._body_label, style="Muted.TLabel").pack(side="left")
        # Reader/Source only make sense for markup, so this row hides otherwise.
        self._modes = ttk.Frame(controls)
        for mode in HTML_MODES:
            ttk.Radiobutton(
                self._modes,
                text=mode,
                value=mode,
                variable=self._html_mode,
                style="Toolbutton",
                command=self._render_body,
            ).pack(side="left", padx=(4, 0))

        self._body = TextView(pane)
        self._body.pack(fill="both", expand=True)
        return pane

    def _build_links(self, master) -> ttk.Frame:
        pane = ttk.Frame(master, padding=(0, 8, 0, 0))
        self._links = KeyValueTable(pane, "TEXT", "HREF", key_width=260)
        self._links.pack(fill="both", expand=True)
        self._links.tree.bind("<Double-1>", lambda _event: self.copy_link())
        self._links.tree.bind("<Return>", lambda _event: self.copy_link())

        actions = ttk.Frame(pane, padding=(0, 8, 0, 0))
        actions.pack(fill="x")
        ttk.Label(
            actions, text="double-click a row to copy its link", style="Muted.TLabel"
        ).pack(side="left")
        self._copy_all = ttk.Button(actions, text="Copy all", command=self.copy_all_links)
        self._copy_all.pack(side="right")
        ttk.Button(actions, text="Copy link", style="Accent.TButton", command=self.copy_link).pack(
            side="right", padx=(0, 8)
        )
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

        self._render_body()
        self._raw.set_content(render_response(exchange))

        links = link_rows(exchange)
        self._links.set_rows(links)
        if links:
            self._notebook.add(self._links_pane, text="Links (%d)" % len(links))
        else:
            self._notebook.hide(self._links_pane)

    def _render_body(self) -> None:
        """(Re)draw the body pane in whichever mode is selected."""
        if self._exchange is None:
            return
        markup = is_html(self._exchange)
        if markup:
            self._modes.pack(side="right")
        else:
            self._modes.pack_forget()
        label, rendered, spans = render_body(self._exchange, self._html_mode.get())
        self._body_label.set(label)
        self._body.set_content(rendered, spans)

    def clear(self) -> None:
        self._exchange = None
        self._badge.configure(text="", foreground=theme.FG_MUTED)
        self._url.configure(text=EMPTY_URL, foreground=theme.FG_MUTED)
        self._timing.configure(text="")
        self._body_label.set("")
        self._modes.pack_forget()
        self._notebook.hide(self._links_pane)
        for table in (self._summary, self._redirects, self._response_headers, self._request_headers, self._links):
            table.clear()
        for view in (self._body, self._raw, self._request_raw):
            view.set_content("")

    # -- actions -----------------------------------------------------------

    def copy_link(self) -> None:
        """Copy the selected link; the table already holds absolute URLs."""
        row = self._links.selected_row()
        if row is None:
            rows = self._links.rows()
            if not rows:
                return
            self._links.tree.selection_set(self._links.tree.get_children()[0])
            row = rows[0]
        self._on_copy(row[1])

    def copy_all_links(self) -> None:
        rows = self._links.rows()
        if rows:
            self._on_copy("\n".join(href for _, href in rows))

    def copy_curl(self) -> None:
        if self._exchange is not None:
            self._on_copy(render_curl(self._exchange))

    def copy_response(self) -> None:
        if self._exchange is not None:
            self._on_copy(render_response(self._exchange))
