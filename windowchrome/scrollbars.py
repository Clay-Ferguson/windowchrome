"""Scroll bars wide enough to grab with the mouse.

Independent of the title bar: no setup, no platform requirement, and nothing
to call before or after the QApplication. A host asks for the wider bars one
scroll area at a time.

Unlike the rest of the library this reads `QPalette.Base` straight from the
application palette, and that is deliberate. `install()` repurposes `Window`
and `WindowText` for the title bar, which is why every *body* color derived
from those two has to come from `body_window_color()`/`body_text_color()`
instead — but `Base` is untouched, so reading it here is correct and routing
it through the body accessors would be wrong.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyle

# Scroll bars are drawn at this multiple of the desktop's own thickness —
# wider bars are easier to grab with the mouse.
SCROLLBAR_SCALE = 2

# A floor for the doubling, in case a style reports an implausibly small
# extent (or none at all) and the result would be a bar too thin to hit.
MIN_SCROLLBAR_EXTENT = 12


def scrollbar_style(base: QColor | None = None) -> str:
    """Qt stylesheet making a scroll bar about twice the usual thickness.

    Applied to the individual scroll bars of a pane rather than to the pane
    itself, so the widget keeps its native rendering and only the bars change.

    The base thickness is read from the active style's own PM_ScrollBarExtent
    rather than assumed, so this doubles whatever the desktop would have
    drawn instead of jumping to a fixed pixel count that happens to be double
    on one theme.

    As with buttons, styling a scroll bar at all opts it out of native
    drawing — so the groove, the handle and the two stepper buttons all have
    to be described here. The steppers are explicitly collapsed to zero:
    left undescribed they would render as blank boxes at each end.

    `base` is the color the bar sits *in*, and the groove is painted with it
    so the bar reads as part of the pane rather than as a stripe laid over
    it. It defaults to the palette's `Base`, which is what a pane normally
    is; a host that paints its field some other color — one derived from
    `Base`, say — passes that color instead, or the groove shows through as
    a visibly different shade against the field.
    """
    extent = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
    thickness = max(extent, MIN_SCROLLBAR_EXTENT) * SCROLLBAR_SCALE

    if base is None:
        base = QApplication.palette().color(QPalette.ColorRole.Base)
    # The handle has to contrast with the pane behind it, and which direction
    # that is depends on the theme: lighten on a dark pane, darken on a light
    # one. Derived from the palette so the bars follow the desktop rather than
    # pinning a gray that only suits one of the two.
    handle = base.lighter(230) if base.lightness() < 128 else base.darker(140)
    hover = handle.lighter(120) if base.lightness() < 128 else handle.darker(115)
    margin = 2
    radius = (thickness - 2 * margin) // 2

    return f"""
        QScrollBar:vertical   {{ background: {base.name()}; width: {thickness}px;
                                 margin: 0; border: none; }}
        QScrollBar:horizontal {{ background: {base.name()}; height: {thickness}px;
                                 margin: 0; border: none; }}
        QScrollBar::handle:vertical   {{ min-height: {thickness * 2}px; }}
        QScrollBar::handle:horizontal {{ min-width: {thickness * 2}px; }}
        QScrollBar::handle {{
            background: {handle.name()};
            border-radius: {radius}px;
            margin: {margin}px;
        }}
        QScrollBar::handle:hover {{ background: {hover.name()}; }}
        /* No stepper arrows: the extra width is for grabbing the handle, and
           zero-sized steppers give the handle the whole length of the bar. */
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0; height: 0; border: none; background: none;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    """


def apply_scrollbars(area, base: QColor | None = None) -> None:
    """Give a scroll area's own bars the wider styling.

    The stylesheet goes on the two QScrollBar children, never on `area`
    itself, so the area keeps whatever native rendering it had. `base` is
    passed straight through to `scrollbar_style()`.
    """
    bars = scrollbar_style(base)
    area.verticalScrollBar().setStyleSheet(bars)
    area.horizontalScrollBar().setStyleSheet(bars)
