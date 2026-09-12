"""Check boxes whose indicator is big enough to hit, with the native tick kept.

Like the scroll bars and the radio buttons: no setup, no platform
requirement, and nothing to call before or after the QApplication. A host
enlarges its boxes one widget at a time.

What is wrong with the native check box is only its *size*: around 13px,
sized for a mouse that never misses. Unlike the radio indicator its colors
are fine, so nothing here touches them.

Why this is a `QProxyStyle` and not a stylesheet, which is the one thing to
know before changing it. The indicator is sized by the style, not by the
font or the widget, so a check box cannot simply be made bigger from the
outside. A stylesheet `QCheckBox::indicator { width: …; height: … }` does
work — geometry is all it sets, so `QStyleSheetStyle` applies the size and
still lets the native style paint the box and its tick.

The trap is that it only works while the rule stays geometry. Add any
*appearance* property — a `border`, a `background` — and Qt takes the
drawing to be yours, stops delegating, and paints only what the rule names.
No CSS property draws a check mark (Qt's answer is `image: url(tick.png)`,
i.e. shipping images for every state), so the box renders empty and a
checked box no longer looks checked. Measured: `width`/`height` alone keeps
the tick; adding `border: 2px solid #444` loses it.

That failure is silent and one word away, which is the reason for the proxy
rather than the stylesheet: overriding the pixel metric changes the
rectangle the native style is handed and never leaves the native drawing
path at all. `radio_style()` goes the stylesheet route because a circle
*is* drawable in CSS and a tick is not.

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
