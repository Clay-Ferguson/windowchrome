"""Shared widget looks for PyQt6 apps on Linux: a viewer, scroll bars, indicators.

Six unrelated things live here, and none of them has any setup or ordering
around the QApplication to get right.

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

A title bar and border drawn by the app, in place of the system's — one
call per top-level window, before it is shown:

    windowchrome.apply_frame(window, colors=FrameColors(...))

See README.md.
"""

from __future__ import annotations

from .checkboxes import CHECKBOX_SCALE, LargeIndicatorStyle, apply_checkboxes
from .frame import (
    CAPTION_BUTTON_WIDTH,
    FRAME_BORDER_WIDTH,
    RESIZE_CORNER_LENGTH,
    RESIZE_GRAB_WIDTH,
    TITLE_BAR_MIN_HEIGHT,
    TITLE_LINE_WIDTH,
    CaptionButton,
    FrameColors,
    TitleBar,
    WindowFrame,
    apply_frame,
    edge_cursor,
    resize_edges,
)
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
    "CAPTION_BUTTON_WIDTH",
    "CHECKBOX_SCALE",
    "FRAME_BORDER_WIDTH",
    "MIN_SCROLLBAR_EXTENT",
    "RADIO_BORDER_WIDTH",
    "RADIO_INDICATOR_SIZE",
    "RESIZE_CORNER_LENGTH",
    "RESIZE_GRAB_WIDTH",
    "SCROLLBAR_SCALE",
    "TITLE_BAR_MIN_HEIGHT",
    "TITLE_LINE_WIDTH",
    "TOGGLE_HEIGHT",
    "TOGGLE_KNOB_COLOR",
    "TOGGLE_KNOB_MARGIN",
    "TOGGLE_OFF_COLOR",
    "TOGGLE_WIDTH",
    "CaptionButton",
    "FrameColors",
    "LargeIndicatorStyle",
    "MarkdownDialog",
    "MarkdownView",
    "TitleBar",
    "ToggleSwitch",
    "WindowFrame",
    "apply_checkboxes",
    "apply_frame",
    "apply_radios",
    "apply_scrollbars",
    "close_markdown_windows",
    "edge_cursor",
    "heading_slug",
    "heading_slugs",
    "radio_style",
    "resize_edges",
    "scrollbar_style",
    "show_markdown",
]
