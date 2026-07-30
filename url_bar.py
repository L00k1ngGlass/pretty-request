"""Top of the window: method, address, Send, and the optional request body."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import profiles
import theme
from fetcher import BODY_METHODS, METHODS
from header_editor import HeaderEditor
from widgets import PlaceholderEntry

PLACEHOLDER = "example.com  ·  type an address and press Enter"
DEFAULT_CONTENT_TYPE = "application/json"


class UrlBar(ttk.Frame):
    def __init__(
        self,
        master,
        *,
        on_send: Callable[[], None],
        on_clear: Callable[[], None],
        profile: str = profiles.DEFAULT_PROFILE,
    ):
        super().__init__(master, padding=(14, 12, 14, 6))
        self._on_send = on_send
        self._method = tk.StringVar(value="GET")
        self._content_type = tk.StringVar(value=DEFAULT_CONTENT_TYPE)
        self._profile = tk.StringVar(value=profile)
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
        self._headers_button = ttk.Button(address, text="Headers", command=self._toggle_headers)
        self._headers_button.pack(side="right", padx=(10, 0))

        self.url_entry = PlaceholderEntry(address, PLACEHOLDER, style="URL.TEntry")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.url_entry.bind("<Return>", lambda _event: self._send_now())

        # Hidden until the Headers button is pressed; the rows survive either way.
        self.headers_editor = HeaderEditor(self, on_change=self._show_profile_note)

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

        # Which client we present ourselves as — servers vary the response on it.
        self._profile_note = ttk.Label(status_row, text="", style="Muted.TLabel")
        profile_box = ttk.Combobox(
            status_row,
            textvariable=self._profile,
            values=profiles.names(),
            state="readonly",
            width=16,
            font=theme.fonts().mono_small,
        )
        profile_box.pack(side="right")
        profile_box.bind("<<ComboboxSelected>>", lambda _event: self._show_profile_note())
        ttk.Label(status_row, text="send as", style="Muted.TLabel").pack(side="right", padx=(12, 6))
        self._profile_note.pack(side="right", padx=(0, 12))
        self._show_profile_note()

    # -- values ------------------------------------------------------------

    def method(self) -> str:
        return self._method.get()

    def url(self) -> str:
        return self.url_entry.value()

    def set_url(self, url: str) -> None:
        self.url_entry.set_value(url)

    def extra_headers(self):
        return self.headers_editor.overrides()

    def drop_headers(self):
        return self.headers_editor.removals()

    def set_method(self, method: str) -> None:
        self._method.set(method.upper())
        self._sync_body_editor()

    def profile(self) -> str:
        return self._profile.get()

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

    def _toggle_headers(self) -> None:
        if self.headers_editor.winfo_manager():
            self.headers_editor.pack_forget()
        else:
            self.headers_editor.pack(fill="x", after=self._address)
        self._show_profile_note()

    def _show_profile_note(self) -> None:
        count = len(
            profiles.headers_for(
                self.profile(),
                url="https://example.com/",
                extra=self.extra_headers(),
                remove=self.drop_headers(),
            )
        )
        custom = self.headers_editor.count()
        text = "%d headers" % count
        if custom:
            text += " · %d custom" % custom
        rejected = self.headers_editor.rejected()
        if rejected:
            text += " · %s set by urllib" % ", ".join(sorted(set(rejected)))
        self._profile_note.configure(text=text)
        self._headers_button.configure(text="Headers (%d)" % custom if custom else "Headers")

    def _sync_body_editor(self) -> None:
        if self.method() in BODY_METHODS:
            self._body_editor.pack(fill="x", after=self._address)
        else:
            self._body_editor.pack_forget()
