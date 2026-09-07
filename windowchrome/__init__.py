"""Shared window furniture for PyQt6 apps on Linux: chrome, a viewer, scroll bars.

Three unrelated things live here, and only the first has an order to get right.

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

Scroll bars about twice the desktop's own thickness, so they are easier to
grab with the mouse. Like the viewer: no setup, no platform requirement:

    windowchrome.apply_scrollbars(area)          # per scroll area
    windowchrome.scrollbar_style()               # the stylesheet on its own

Radio buttons with an enlarged, visibly outlined indicator, for the same
reasons and with the same lack of setup:

    windowchrome.apply_radios(*buttons)          # per button
    windowchrome.radio_style()                   # the stylesheet on its own

Check boxes with an enlarged indicator, keeping Qt's own tick — a style
rather than a stylesheet, for the reason given in the module:

    windowchrome.apply_checkboxes(*boxes)        # per box
    windowchrome.LargeIndicatorStyle()           # the style on its own

An on/off switch to put where a check box would have gone — a painted
widget rather than a stylesheet, because the shape itself differs, but
with the same lack of setup:

    windowchrome.ToggleSwitch(parent, on_color=...)

See README.md.
"""

from __future__ import annotations

from .checkboxes import CHECKBOX_SCALE, LargeIndicatorStyle, apply_checkboxes
from .markdowndialog import MarkdownDialog, close_markdown_windows, show_markdown
from .markdownview import MarkdownView, heading_slug, heading_slugs
from .radiobuttons import (
    RADIO_BORDER_WIDTH,
    RADIO_INDICATOR_SIZE,
    apply_radios,
    radio_style,
)
from .scrollbars import (
    MIN_SCROLLBAR_EXTENT,
    SCROLLBAR_SCALE,
    apply_scrollbars,
    scrollbar_style,
)
from .theme import DEFAULT_THEME, ChromeTheme, theme
from .titlebar import (
    DECORATION_ENV,
    body_text_color,
    body_window_color,
    configure,
    install,
)
from .toggleswitch import (
    TOGGLE_HEIGHT,
    TOGGLE_KNOB_COLOR,
    TOGGLE_KNOB_MARGIN,
    TOGGLE_OFF_COLOR,
    TOGGLE_WIDTH,
    ToggleSwitch,
)

__all__ = [
    "CHECKBOX_SCALE",
    "DECORATION_ENV",
    "DEFAULT_THEME",
    "MIN_SCROLLBAR_EXTENT",
    "RADIO_BORDER_WIDTH",
    "RADIO_INDICATOR_SIZE",
    "SCROLLBAR_SCALE",
    "TOGGLE_HEIGHT",
    "TOGGLE_KNOB_COLOR",
    "TOGGLE_KNOB_MARGIN",
    "TOGGLE_OFF_COLOR",
    "TOGGLE_WIDTH",
    "ChromeTheme",
    "LargeIndicatorStyle",
    "MarkdownDialog",
    "MarkdownView",
    "ToggleSwitch",
    "apply_checkboxes",
    "apply_radios",
    "apply_scrollbars",
    "body_text_color",
    "body_window_color",
    "close_markdown_windows",
    "configure",
    "heading_slug",
    "heading_slugs",
    "install",
    "radio_style",
    "scrollbar_style",
    "show_markdown",
    "theme",
]
