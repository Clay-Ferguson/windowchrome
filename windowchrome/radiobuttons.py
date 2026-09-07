"""Radio buttons big enough to see, with an indicator that is actually visible.

Independent of the title bar, like the scroll bars: no setup, no platform
requirement, and nothing to call before or after the QApplication. A host
styles its buttons one group at a time.

Two things are wrong with the native indicator under the dark themes these
apps run in. It is small — around 13px, sized for a mouse and not for a
glance — and its ring is drawn in a near-black that all but disappears
against a dark dialog. Both are fixed here by drawing the indicator from a
stylesheet instead.

As with the scroll bars, this reads `QPalette.Base` and `QPalette.Text`
straight from the application palette, and that is deliberate: `install()`
repurposes `Window` and `WindowText` for the title bar, so only colors
derived from *those two* have to come from `body_window_color()` /
`body_text_color()`. `Base` and `Text` are untouched.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# The drawn diameter of the indicator, in pixels. Roughly the native size
# doubled — the same reasoning as the scroll bars, and enough that "which one
# is selected" is answerable from across the desk.
RADIO_INDICATOR_SIZE = 22

# How thick the ring around it is drawn.
RADIO_BORDER_WIDTH = 2


def radio_style(
    base: QColor | None = None,
    point_size: int | None = None,
    size: int = RADIO_INDICATOR_SIZE,
) -> str:
    """Qt stylesheet drawing an enlarged, clearly outlined radio indicator.

    Styling `::indicator` at all opts the button out of the native drawing,
    so the circle, its ring and the checked state all have to be described
    here — there is no "keep the native dot, just bigger".

    The ring, and the fill of the checked state, take the palette's `Text`
    color, so the indicator reads as bright as the label beside it and
    follows the desktop between a light theme and a dark one instead of
    pinning a gray that suits only one.

    `base` is the color painted *inside* an unchecked circle, defaulting to
    the palette's `Base`; a host whose dialog fields are some other color —
    one derived from `Base`, say — passes that, exactly as it would to
    `apply_scrollbars()`. `point_size` sets the label's font size and is
    left to the widget's own font when omitted.

    The checked state is a solidly filled circle rather than the native ring
    with a smaller dot inside it: a stylesheet has one border per element,
    so a gap between ring and dot cannot be drawn without giving up the ring
    that makes the unchecked state visible in the first place. A filled
    circle in the same bright color is unambiguous at this size.
    """
    if base is None:
        base = QApplication.palette().color(QPalette.ColorRole.Base)
    outline = QApplication.palette().color(QPalette.ColorRole.Text)

    font = f" font-size: {point_size}pt;" if point_size is not None else ""
    radius = size // 2 + RADIO_BORDER_WIDTH

    return (
        f"QRadioButton {{{font} spacing: 10px; }}"
        f" QRadioButton::indicator {{ width: {size}px; height: {size}px;"
        f" border: {RADIO_BORDER_WIDTH}px solid {outline.name()};"
        f" border-radius: {radius}px;"
        f" background-color: {base.name()}; }}"
        f" QRadioButton::indicator:checked {{ background-color: {outline.name()}; }}"
    )


def apply_radios(
    *buttons,
    base: QColor | None = None,
    point_size: int | None = None,
    size: int = RADIO_INDICATOR_SIZE,
) -> None:
    """Give each radio button the enlarged indicator styling.

    The sheet is built once and set on every button passed, so a group of
    them costs one string. The arguments are passed straight through to
    `radio_style()`.
    """
    sheet = radio_style(base, point_size, size)
    for button in buttons:
        button.setStyleSheet(sheet)
