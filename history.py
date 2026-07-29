"""Left pane: the filterable list of exchanges made so far."""

from __future__ import annotations

from tkinter import ttk
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit

import theme
from exchange import Exchange
from formatting import matches
from widgets import PlaceholderEntry


class History(ttk.Frame):
    """Owns the exchanges it displays and its own filter."""

    def __init__(self, master, on_select: Callable[[Exchange], None]):
        super().__init__(master)
        self._on_select = on_select
        self._exchanges: List[Exchange] = []
        self._by_item: Dict[str, Exchange] = {}

        self._filter = PlaceholderEntry(self, "filter by status, method, url or header…")
        self._filter.pack(fill="x", pady=(0, 8))
        self._filter.bind("<KeyRelease>", lambda _event: self.refresh())

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            holder, columns=("status", "method", "url", "time"), show="headings", selectmode="browse"
        )
        self.tree.heading("status", text="STATUS")
        self.tree.heading("method", text="METHOD")
        self.tree.heading("url", text="URL")
        self.tree.heading("time", text="TIME")
        self.tree.column("status", width=64, minwidth=60, stretch=False, anchor="w")
        self.tree.column("method", width=76, minwidth=70, stretch=False, anchor="w")
        self.tree.column("url", width=260, minwidth=140, stretch=True, anchor="w")
        self.tree.column("time", width=72, minwidth=64, stretch=False, anchor="e")
        for status_class, color in theme.STATUS_COLORS.items():
            self.tree.tag_configure("status%d" % status_class, foreground=color)
        self.tree.tag_configure("failed", foreground=theme.ERROR)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- data --------------------------------------------------------------

    def add(self, exchange: Exchange) -> bool:
        """Store an exchange; returns whether it passed the filter and was shown."""
        self._exchanges.append(exchange)
        if not matches(exchange, self._filter.value()):
            return False
        self._insert(exchange)
        return True

    def clear(self) -> None:
        self._exchanges.clear()
        self._by_item.clear()
        self.tree.delete(*self.tree.get_children())

    def refresh(self) -> None:
        """Rebuild the visible rows, keeping the current selection if it survives."""
        selected = self.selected()
        self._by_item.clear()
        self.tree.delete(*self.tree.get_children())
        needle = self._filter.value()
        for exchange in self._exchanges:
            if matches(exchange, needle):
                self._insert(exchange)
        if selected is not None:
            self.select(selected)

    def selected(self) -> Optional[Exchange]:
        selection = self.tree.selection()
        return self._by_item.get(selection[0]) if selection else None

    def select(self, exchange: Exchange) -> None:
        for item, candidate in self._by_item.items():
            if candidate is exchange:
                self.tree.selection_set(item)
                self.tree.see(item)
                return

    def select_last(self) -> None:
        items = self.tree.get_children()
        if items:
            self.tree.selection_set(items[-1])
            self.tree.see(items[-1])

    # -- internals ---------------------------------------------------------

    def _insert(self, exchange: Exchange) -> None:
        tag = "failed" if exchange.error is not None else "status%d" % (exchange.status // 100)
        item = self.tree.insert(
            "",
            "end",
            values=(
                exchange.status if exchange.ok else "—",
                exchange.method,
                _short_url(exchange.url),
                "%d ms" % round(exchange.elapsed_ms),
            ),
            tags=(tag,),
        )
        self._by_item[item] = exchange

    def _selection_changed(self, _event=None) -> None:
        exchange = self.selected()
        if exchange is not None:
            self._on_select(exchange)


def _short_url(url: str) -> str:
    """Drop the scheme — the host and path are what you scan for."""
    parts = urlsplit(url)
    target = parts.path if parts.path != "/" else ""
    if parts.query:
        target += "?" + parts.query
    return parts.netloc + target
