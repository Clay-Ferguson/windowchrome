"""Colored title bar for PyQt6 apps on Linux/Wayland.

Five names, and two of them are setup calls that have to happen at different
moments:

    windowchrome.configure(theme)      # BEFORE QApplication is constructed
    windowchrome.install(app)          # AFTER QApplication, AFTER palette tuning
    windowchrome.body_window_color()   # for any derived body color
    windowchrome.body_text_color()     # ... and any derived body text color
    windowchrome.ChromeTheme(...)      # the colors, and the decoration plugin

Wayland only, in effect: the title bar is colorable because Qt draws the
decoration in-process there, and `install()` is a no-op anywhere else. See
README.md.
"""

from __future__ import annotations

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
    "body_text_color",
    "body_window_color",
    "configure",
    "install",
    "theme",
]
