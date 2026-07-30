"""An editor for custom request headers, layered over the chosen profile."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable, List, Optional, Tuple

import theme
from profiles import PROTECTED_HEADERS
from widgets import ScrollableFrame

Header = Tuple[str, str]
HINT = "a name the profile already sends is replaced in place · blank value removes it"
SUGGESTIONS = (
    "Authorization",
    "Cookie",
    "Referer",
    "Accept",
    "Accept-Language",
    "Content-Type",
    "If-None-Match",
    "X-Requested-With",
)


@dataclass
class _Row:
    frame: ttk.Frame
    enabled: tk.BooleanVar
    name: tk.StringVar
    value: tk.StringVar


class HeaderEditor(ttk.Frame):
    """Rows of name/value pairs that override or remove profile headers."""

    def __init__(self, master, *, on_change: Optional[Callable[[], None]] = None):
        super().__init__(master, padding=(0, 8, 0, 0))
        self._on_change = None  # stays quiet until the first row exists
        self._rows: List[_Row] = []

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="custom headers", style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="+ Add header", command=self.add_row).pack(side="right")
        ttk.Label(top, text=HINT, style="Muted.TLabel").pack(side="right", padx=(0, 12))

        self._rows_area = ScrollableFrame(self)
        self._rows_area.configure(height=110)
        self._rows_area.pack(fill="x")
        self.add_row()
        self._on_change = on_change

    # -- rows --------------------------------------------------------------

    def add_row(self, name: str = "", value: str = "") -> None:
        row = ttk.Frame(self._rows_area.body, style="Panel.TFrame")
        row.pack(fill="x", pady=2)
        state = _Row(row, tk.BooleanVar(value=True), tk.StringVar(value=name), tk.StringVar(value=value))

        ttk.Checkbutton(row, variable=state.enabled).pack(side="left")
        name_box = ttk.Combobox(
            row, textvariable=state.name, values=list(SUGGESTIONS), width=22,
            font=theme.fonts().mono_small,
        )
        name_box.pack(side="left", padx=(6, 6))
        ttk.Button(row, text="✕", width=3, command=lambda: self._remove(state)).pack(side="right")
        ttk.Entry(row, textvariable=state.value, font=theme.fonts().mono_small).pack(
            side="left", fill="x", expand=True
        )

        for variable in (state.enabled, state.name, state.value):
            variable.trace_add("write", lambda *_: self._changed())
        self._rows.append(state)
        self._changed()

    def _remove(self, state: _Row) -> None:
        state.frame.destroy()
        self._rows.remove(state)
        if not self._rows:
            self.add_row()
        self._changed()

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    # -- values ------------------------------------------------------------

    def overrides(self) -> List[Header]:
        """Enabled rows that carry a value: added, or replacing a profile header."""
        return [
            (name, row.value.get().strip())
            for row in self._rows
            for name in [row.name.get().strip()]
            if row.enabled.get() and name and row.value.get().strip() and not _protected(name)
        ]

    def removals(self) -> List[str]:
        """Enabled rows with a name but no value: drop that header entirely."""
        return [
            name
            for row in self._rows
            for name in [row.name.get().strip()]
            if row.enabled.get() and name and not row.value.get().strip() and not _protected(name)
        ]

    def count(self) -> int:
        return len(self.overrides()) + len(self.removals())

    def rejected(self) -> List[str]:
        """Names the transport will not let us touch, so the UI can say so."""
        return [
            name
            for row in self._rows
            for name in [row.name.get().strip()]
            if row.enabled.get() and name and _protected(name)
        ]


def _protected(name: str) -> bool:
    return name.lower() in PROTECTED_HEADERS
