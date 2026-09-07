"""Check boxes whose indicator is big enough to hit, with the native tick kept.

Independent of the title bar, like the scroll bars and the radio buttons: no
setup, no platform requirement, and nothing to call before or after the
QApplication. A host enlarges its boxes one widget at a time.

What is wrong with the native check box is only its *size*: around 13px,
sized for a mouse that never misses. Unlike the radio indicator its colors
are fine, so nothing here touches them.

Why this is a `QProxyStyle` and not a stylesheet, which is the one thing to
know before changing it. The indicator is sized by the style, not by the
font or the widget, so a check box cannot simply be made bigger from the
outside. A stylesheet *can* set `::indicator`'s width and height — but
styling that sub-control at all takes over its drawing, and the check mark
goes with it: no stylesheet draws a tick without shipping an image, so the
box comes out never looking ticked. That is exactly the trade `radio_style()`
accepts, because a filled circle is drawable and a tick is not. Overriding
the pixel metric instead keeps Qt's own rendering and changes only the
rectangle it is asked to fill.

Nothing here reads the palette at all, for the same reason: the native
drawing already follows the theme.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QProxyStyle, QStyle

# How much bigger than the desktop's own a check box's indicator is drawn.
# Same reasoning as the scroll bars: a bigger target is an easier one to hit.
CHECKBOX_SCALE = 2


class LargeIndicatorStyle(QProxyStyle):
    """A style that reports check-box indicators at `scale` times native size.

    Default-constructed on purpose: with no base style it proxies whatever
    QApplication is using at the time, and, unlike the constructor that takes
    a style, it does not take ownership of the application's shared one.

    Only the two indicator metrics are touched; every other metric is the
    base style's answer, unchanged.
    """

    def __init__(self, scale: int = CHECKBOX_SCALE) -> None:
        super().__init__()
        self._scale = scale

    def pixelMetric(self, metric, option=None, widget=None):  # noqa: N802 (Qt)
        size = super().pixelMetric(metric, option, widget)
        if metric in (
            QStyle.PixelMetric.PM_IndicatorWidth,
            QStyle.PixelMetric.PM_IndicatorHeight,
        ):
            return size * self._scale
        return size


def apply_checkboxes(*boxes: QCheckBox, scale: int = CHECKBOX_SCALE) -> None:
    """Draw each box's indicator larger, leaving its label at the normal size.

    A style is built per box and parented to it, rather than one shared style
    or one installed on the application: this is one widget's affordance, not
    a change of theme. The parenting is also what keeps the style alive —
    `setStyle()` does not take ownership, and a style collected out from
    under a live widget crashes it.
    """
    for box in boxes:
        style = LargeIndicatorStyle(scale)
        style.setParent(box)
        box.setStyle(style)
