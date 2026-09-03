"""Shared window furniture for PyQt6 apps on Linux: chrome, and a doc viewer.

Two unrelated things live here, and only the first has an order to get right.

The colored title bar — Wayland only, in effect, because that is where Qt
draws the decoration in-process:

    windowchrome.configure(theme)      # BEFORE QApplication is constructed
    windowchrome.install(app)          # AFTER QApplication, AFTER palette tuning
    windowchrome.body_window_color()   # for any derived body color
    windowchrome.body_text_color()     # ... and any derived body text color
    windowchrome.ChromeTheme(...)      # the colors, and the decoration plugin

The markdown viewer, for showing an application's own documentation inside
it. No setup, no platform requirement, and no dependency on the chrome:

    windowchrome.show_markdown(path, parent, button_factory=...)
    windowchrome.MarkdownView(...)     # the widget on its own, outside a dialog
    windowchrome.close_markdown_windows()

See README.md.
"""

from __future__ import annotations

from .markdowndialog import MarkdownDialog, close_markdown_windows, show_markdown
from .markdownview import MarkdownView, heading_slug, heading_slugs
from .theme import DEFAULT_THEME, ChromeTheme, theme
from .titlebar import (
    DECORATION_ENV,
    body_text_color,
    body_window_color,
    configure,
    install,
)

__all__ = [
    "DECORATION_ENV",
    "DEFAULT_THEME",
    "ChromeTheme",
    "MarkdownDialog",
    "MarkdownView",
    "body_text_color",
    "body_window_color",
    "close_markdown_windows",
    "configure",
    "heading_slug",
    "heading_slugs",
    "install",
    "show_markdown",
    "theme",
]
