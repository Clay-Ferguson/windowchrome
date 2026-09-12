"""Shared widget looks for PyQt6 apps on Linux: a viewer, scroll bars, indicators.

Five unrelated things live here, and none of them has any setup or ordering
to get right.

The markdown viewer, for showing an application's own documentation inside
it:

    windowchrome.show_markdown(path, parent, button_factory=...)
    windowchrome.MarkdownView(...)     # the widget on its own, outside a dialog
    windowchrome.close_markdown_windows()

Scroll bars about twice the desktop's own thickness, so they are easier to
grab with the mouse:

    windowchrome.apply_scrollbars(area)          # per scroll area
    windowchrome.scrollbar_style()               # the stylesheet on its own

Radio buttons with an enlarged, visibly outlined indicator:

    windowchrome.apply_radios(*buttons)          # per button
    windowchrome.radio_style()                   # the stylesheet on its own

Check boxes with an enlarged indicator, keeping Qt's own tick — a style
rather than a stylesheet, for the reason given in the module:

    windowchrome.apply_checkboxes(*boxes)        # per box
    windowchrome.LargeIndicatorStyle()           # the style on its own

An on/off switch to put where a check box would have gone — a painted
widget rather than a stylesheet, because the shape itself differs:

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
    "MIN_SCROLLBAR_EXTENT",
    "RADIO_BORDER_WIDTH",
    "RADIO_INDICATOR_SIZE",
    "SCROLLBAR_SCALE",
    "TOGGLE_HEIGHT",
    "TOGGLE_KNOB_COLOR",
    "TOGGLE_KNOB_MARGIN",
    "TOGGLE_OFF_COLOR",
    "TOGGLE_WIDTH",
    "LargeIndicatorStyle",
    "MarkdownDialog",
    "MarkdownView",
    "ToggleSwitch",
    "apply_checkboxes",
    "apply_radios",
    "apply_scrollbars",
    "close_markdown_windows",
    "heading_slug",
    "heading_slugs",
    "radio_style",
    "scrollbar_style",
    "show_markdown",
]
