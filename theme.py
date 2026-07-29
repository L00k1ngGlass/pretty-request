"""Colours, fonts and ttk styles. Everything visual is decided here."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk
from typing import Optional, Sequence

BG = "#14161a"
BG_PANEL = "#1a1d23"
BG_ROW_ALT = "#171a20"
BG_INPUT = "#22262e"
BG_SELECT = "#2c3340"
FG = "#e6e9ef"
FG_MUTED = "#8b93a7"
BORDER = "#2a2e37"
ACCENT = "#7aa2f7"
OK = "#7ee787"
ERROR = "#f7768e"

METHOD_COLORS = {
    "GET": "#7ee787",
    "POST": "#7aa2f7",
    "PUT": "#e3b341",
    "PATCH": "#d2a8ff",
    "DELETE": "#f7768e",
    "HEAD": "#56d4dd",
    "OPTIONS": "#56d4dd",
    "TRACE": "#8b93a7",
}

STATUS_COLORS = {
    1: "#56d4dd",  # informational
    2: "#7ee787",  # success
    3: "#d2a8ff",  # redirect
    4: "#e3b341",  # client error
    5: "#f7768e",  # server error
}

MONO_STACK = ("SF Mono", "Menlo", "Monaco", "Consolas", "DejaVu Sans Mono", "Courier")
UI_STACK = ("SF Pro Text", "Helvetica Neue", "Segoe UI", "DejaVu Sans", "Helvetica")


@dataclass(frozen=True)
class Fonts:
    ui: tkfont.Font
    ui_bold: tkfont.Font
    mono: tkfont.Font
    mono_small: tkfont.Font
    mono_bold: tkfont.Font


_fonts: Optional[Fonts] = None


def fonts() -> Fonts:
    """The font set built by :func:`apply`."""
    if _fonts is None:
        raise RuntimeError("theme.apply() must be called on the root window first")
    return _fonts


def method_color(method: str) -> str:
    return METHOD_COLORS.get(method.upper(), FG)


def status_color(status: int) -> str:
    """Colour for a status code; ``0`` means the request never completed."""
    return STATUS_COLORS.get(status // 100, ERROR)


def apply(root: tk.Misc) -> Fonts:
    """Install the palette on ``root`` and build the shared fonts."""
    global _fonts

    ui_family = _first_available(root, UI_STACK)
    mono_family = _first_available(root, MONO_STACK)
    _fonts = Fonts(
        ui=tkfont.Font(root=root, family=ui_family, size=12),
        ui_bold=tkfont.Font(root=root, family=ui_family, size=14, weight="bold"),
        mono=tkfont.Font(root=root, family=mono_family, size=12),
        mono_small=tkfont.Font(root=root, family=mono_family, size=11),
        mono_bold=tkfont.Font(root=root, family=mono_family, size=13, weight="bold"),
    )

    style = ttk.Style(root)
    style.theme_use("clam")  # the only built-in theme that honours custom colours
    _configure(style, _fonts)

    # The combobox dropdown is a plain Tk listbox and ignores ttk styling.
    root.option_add("*TCombobox*Listbox.background", BG_INPUT)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", BG_SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", FG)
    root.option_add("*TCombobox*Listbox.font", _fonts.mono)
    return _fonts


def _first_available(root: tk.Misc, candidates: Sequence[str]) -> str:
    available = set(tkfont.families(root))
    for family in candidates:
        if family in available:
            return family
    return candidates[-1]


def _configure(style: ttk.Style, f: Fonts) -> None:
    style.configure(".", background=BG, foreground=FG, font=f.ui)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=BG_PANEL)

    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=f.ui_bold)

    style.configure(
        "TButton",
        background=BG_INPUT,
        foreground=FG,
        bordercolor=BORDER,
        focuscolor=BG_INPUT,
        relief="flat",
        padding=(12, 5),
    )
    style.map(
        "TButton",
        background=[("active", BG_SELECT), ("pressed", BG_SELECT)],
        foreground=[("disabled", FG_MUTED)],
    )

    style.configure("Accent.TButton", background=ACCENT, foreground="#0d1017")
    style.map(
        "Accent.TButton",
        background=[("active", "#8fb3ff"), ("pressed", "#6b93e8"), ("disabled", BG_INPUT)],
        foreground=[("disabled", FG_MUTED)],
    )

    style.configure(
        "TCombobox",
        fieldbackground=BG_INPUT,
        background=BG_INPUT,
        foreground=FG,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        arrowcolor=FG_MUTED,
        selectbackground=BG_INPUT,
        selectforeground=FG,
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_INPUT)],
        foreground=[("readonly", FG)],
        background=[("active", BG_SELECT)],
    )

    style.configure(
        "URL.TEntry",
        fieldbackground=BG_INPUT,
        foreground=FG,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=FG,
        padding=8,
        font=f.mono,
    )

    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        foreground=FG,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=FG,
        padding=5,
    )

    style.configure("TCheckbutton", background=BG, foreground=FG_MUTED, focuscolor=BG)
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        foreground=[("active", FG)],
        indicatorcolor=[("selected", ACCENT), ("!selected", BG_INPUT)],
    )

    style.configure(
        "Treeview",
        background=BG_PANEL,
        fieldbackground=BG_PANEL,
        foreground=FG,
        bordercolor=BORDER,
        borderwidth=0,
        rowheight=26,
        font=f.mono_small,
    )
    style.map("Treeview", background=[("selected", BG_SELECT)], foreground=[("selected", FG)])
    style.configure(
        "Treeview.Heading",
        background=BG,
        foreground=FG_MUTED,
        relief="flat",
        padding=(8, 6),
        font=f.ui,
    )
    style.map("Treeview.Heading", background=[("active", BG_INPUT)])

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", background=BG, foreground=FG_MUTED, padding=(14, 7), borderwidth=0)
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG_PANEL)],
        foreground=[("selected", FG)],
    )

    for orient in ("Vertical", "Horizontal"):
        style.configure(
            "%s.TScrollbar" % orient,
            background=BG_INPUT,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=FG_MUTED,
            relief="flat",
        )
        style.map("%s.TScrollbar" % orient, background=[("active", BG_SELECT)])

    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=8, gripcount=0)
