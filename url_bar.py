"""Top of the window: method, address, Send, and the optional request body."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import theme
from fetcher import BODY_METHODS, METHODS
from widgets import PlaceholderEntry

PLACEHOLDER = "example.com  ·  type an address and press Enter"
DEFAULT_CONTENT_TYPE = "application/json"


class UrlBar(ttk.Frame):
    def __init__(self, master, *, on_send: Callable[[], None], on_clear: Callable[[], None]):
        super().__init__(master, padding=(14, 12, 14, 6))
        self._on_send = on_send
        self._method = tk.StringVar(value="GET")
        self._content_type = tk.StringVar(value=DEFAULT_CONTENT_TYPE)
        self._status = tk.StringVar(value="ready")

        address = self._address = ttk.Frame(self)
        address.pack(fill="x")

        self._method_box = ttk.Combobox(
            address,
            textvariable=self._method,
            values=list(METHODS),
            state="readonly",
            width=8,
            font=theme.fonts().mono,
        )
        self._method_box.pack(side="left")
        self._method_box.bind("<<ComboboxSelected>>", lambda _event: self._sync_body_editor())

        self._send = ttk.Button(address, text="Send", style="Accent.TButton", command=self._send_now)
        self._send.pack(side="right", padx=(10, 0))
        ttk.Button(address, text="Clear", command=on_clear).pack(side="right", padx=(10, 0))

        self.url_entry = PlaceholderEntry(address, PLACEHOLDER, style="URL.TEntry")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.url_entry.bind("<Return>", lambda _event: self._send_now())

        # Only shown for methods that carry a body.
        self._body_editor = ttk.Frame(self, padding=(0, 8, 0, 0))
        type_row = ttk.Frame(self._body_editor)
        type_row.pack(fill="x", pady=(0, 4))
        ttk.Label(type_row, text="body", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Entry(type_row, textvariable=self._content_type, width=32).pack(side="left")
        self._body = tk.Text(
            self._body_editor,
            height=4,
            wrap="none",
            background=theme.BG_INPUT,
            foreground=theme.FG,
            insertbackground=theme.FG,
            selectbackground=theme.BG_SELECT,
            font=theme.fonts().mono,
            relief="flat",
            highlightthickness=0,
            padx=10,
            pady=8,
        )
        self._body.pack(fill="x")

        status_row = ttk.Frame(self, padding=(0, 8, 0, 0))
        status_row.pack(fill="x")
        self._dot = tk.Canvas(status_row, width=10, height=10, background=theme.BG, highlightthickness=0)
        self._dot.create_oval(1, 1, 9, 9, fill=theme.FG_MUTED, outline="", tags="dot")
        self._dot.pack(side="left", padx=(0, 8))
        ttk.Label(status_row, textvariable=self._status, style="Muted.TLabel").pack(side="left")

    # -- values ------------------------------------------------------------

    def method(self) -> str:
        return self._method.get()

    def url(self) -> str:
        return self.url_entry.value()

    def set_url(self, url: str) -> None:
        self.url_entry.set_value(url)

    def content_type(self) -> str:
        return self._content_type.get().strip()

    def body(self) -> Optional[bytes]:
        if self.method() not in BODY_METHODS:
            return None
        text = self._body.get("1.0", "end").strip()
        return text.encode("utf-8") if text else None

    def focus_url(self) -> None:
        self.url_entry.focus_set()

    # -- state -------------------------------------------------------------

    @property
    def status(self):
        """Current ``(text, colour)``, so callers can restore it after a flash."""
        return self._status.get(), self._dot.itemcget("dot", "fill")

    def set_status(self, text: str, color: str) -> None:
        self._status.set(text)
        self._dot.itemconfigure("dot", fill=color)

    def set_busy(self, busy: bool) -> None:
        self._send.configure(text="Sending…" if busy else "Send", state="disabled" if busy else "normal")

    # -- internals ---------------------------------------------------------

    def _send_now(self) -> None:
        if str(self._send.cget("state")) != "disabled":
            self._on_send()

    def _sync_body_editor(self) -> None:
        if self.method() in BODY_METHODS:
            self._body_editor.pack(fill="x", after=self._address)
        else:
            self._body_editor.pack_forget()
