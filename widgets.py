"""Small reusable Tk building blocks shared by the panes."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Tuple

import theme


class PlaceholderEntry(ttk.Entry):
    """An entry that shows greyed-out hint text while it is empty."""

    def __init__(self, master, placeholder: str, **kwargs):
        super().__init__(master, **kwargs)
        self._placeholder = placeholder
        self._showing = False
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show()

    def value(self) -> str:
        """The real text — empty string while the placeholder is showing."""
        return "" if self._showing else self.get()

    def set_value(self, text: str) -> None:
        self._showing = False
        self.delete(0, "end")
        self.configure(foreground=theme.FG)
        self.insert(0, text)
        if not text:
            self._show()

    def _show(self) -> None:
        if not self.get():
            self._showing = True
            self.insert(0, self._placeholder)
            self.configure(foreground=theme.FG_MUTED)

    def _on_focus_in(self, _event=None) -> None:
        if self._showing:
            self._showing = False
            self.delete(0, "end")
            self.configure(foreground=theme.FG)

    def _on_focus_out(self, _event=None) -> None:
        self._show()


class KeyValueTable(ttk.Frame):
    """A two-column read-only table with zebra striping."""

    def __init__(self, master, key_heading: str, value_heading: str, key_width: int = 200):
        super().__init__(master, style="Panel.TFrame")
        self.tree = ttk.Treeview(self, columns=("key", "value"), show="headings", selectmode="browse")
        self.tree.heading("key", text=key_heading)
        self.tree.heading("value", text=value_heading)
        self.tree.column("key", width=key_width, minwidth=120, stretch=False, anchor="w")
        self.tree.column("value", width=320, minwidth=160, stretch=True, anchor="w")
        self.tree.tag_configure("key", foreground=theme.ACCENT)
        self.tree.tag_configure("alt", background=theme.BG_ROW_ALT)

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def set_rows(self, rows: Iterable[Tuple[str, str]]) -> None:
        self.clear()
        for index, (key, value) in enumerate(rows):
            tags = ("key", "alt") if index % 2 else ("key",)
            self.tree.insert("", "end", values=(key, value), tags=tags)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())


class TextView(ttk.Frame):
    """A read-only monospace text area with both scrollbars."""

    def __init__(self, master):
        super().__init__(master, style="Panel.TFrame")
        self.text = tk.Text(
            self,
            wrap="none",
            background=theme.BG_PANEL,
            foreground=theme.FG,
            insertbackground=theme.FG,
            selectbackground=theme.BG_SELECT,
            font=theme.fonts().mono,
            relief="flat",
            highlightthickness=0,
            padx=12,
            pady=10,
        )
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        xscroll = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        for kind, color in theme.SYNTAX.items():
            self.text.tag_configure(kind, foreground=color)
        self.text.configure(state="disabled")

    def set_content(self, content: str, spans: Iterable[Tuple[str, int, int]] = ()) -> None:
        """Replace the contents, optionally colouring ``(kind, start, end)`` spans."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        for kind in theme.SYNTAX:
            self.text.tag_remove(kind, "1.0", "end")
        for kind, start, end in spans:
            self.text.tag_add(kind, "1.0 + %d chars" % start, "1.0 + %d chars" % end)
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
