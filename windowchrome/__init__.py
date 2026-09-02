"""Colored title bar and window border for PyQt6 apps on Linux/Wayland.

Six names, and two of them are setup calls that have to happen at different
moments:

    windowchrome.configure(theme)      # BEFORE QApplication is constructed
    windowchrome.install(app)          # AFTER QApplication, AFTER palette tuning
    windowchrome.bordered_body(frame)  # per top-level window; returns the body
    windowchrome.body_window_color()   # for any derived body color
    windowchrome.menu_bar_style()      # concatenate into the host's menu sheet
    windowchrome.ChromeTheme(...)      # colors, border width, decoration plugin

The border works everywhere; the title bar color is Wayland-only, because it
depends on Qt drawing the decoration in-process. See README.md.
"""

from __future__ import annotations

from .border import (
    BODY_OBJECT_NAME,
    FRAME_OBJECT_NAME,
    bordered_body,
    menu_bar_style,
    window_border_style,
)
from .theme import DEFAULT_THEME, ChromeTheme, theme
from .titlebar import DECORATION_ENV, body_window_color, configure, install

__all__ = [
    "BODY_OBJECT_NAME",
    "DECORATION_ENV",
    "DEFAULT_THEME",
    "FRAME_OBJECT_NAME",
    "ChromeTheme",
    "body_window_color",
    "bordered_body",
    "configure",
    "install",
    "menu_bar_style",
    "theme",
    "window_border_style",
]
