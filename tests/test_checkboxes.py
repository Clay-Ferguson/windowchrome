"""The enlarged check-box indicator: the metric, what it leaves alone, and
where the style lands.

Claims about the style object and about which widget it was set on — nothing
here is about pixels Qt painted. The one thing worth stating outright is
what the proxy does *not* do: every metric but the two indicator ones has to
come back untouched, or enlarging a check box quietly resizes the rest of
the widget's furniture with it.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QCheckBox, QStyle

from windowchrome import CHECKBOX_SCALE, LargeIndicatorStyle, apply_checkboxes

INDICATOR = (
    QStyle.PixelMetric.PM_IndicatorWidth,
    QStyle.PixelMetric.PM_IndicatorHeight,
)


def native(metric):
    return QApplication.style().pixelMetric(metric)


# -- the metric -------------------------------------------------------------


def test_the_indicator_is_scaled_by_the_default(qapp):
    style = LargeIndicatorStyle()
    for metric in INDICATOR:
        assert style.pixelMetric(metric) == native(metric) * CHECKBOX_SCALE


def test_a_scale_can_be_asked_for(qapp):
    style = LargeIndicatorStyle(3)
    for metric in INDICATOR:
        assert style.pixelMetric(metric) == native(metric) * 3


def test_the_default_is_bigger_than_the_desktop_would_have_drawn(qapp):
    assert CHECKBOX_SCALE > 1


def test_every_other_metric_is_left_alone(qapp):
    """The proxy answers for two metrics and forwards the rest. A style that
    scaled anything else would grow the widget's spacing and frames too."""
    style = LargeIndicatorStyle()
    others = (
        QStyle.PixelMetric.PM_ExclusiveIndicatorWidth,
        QStyle.PixelMetric.PM_ButtonMargin,
        QStyle.PixelMetric.PM_DefaultFrameWidth,
        QStyle.PixelMetric.PM_ScrollBarExtent,
    )
    for metric in others:
        assert style.pixelMetric(metric) == native(metric)


def test_the_radio_indicator_is_not_touched(qapp):
    """A check box's indicator and a radio's are separate metrics; this
    helper is about the first only, and `radio_style()` about the second."""
    style = LargeIndicatorStyle()
    metric = QStyle.PixelMetric.PM_ExclusiveIndicatorWidth
    assert style.pixelMetric(metric) == native(metric)


# -- applying it ------------------------------------------------------------


def test_every_box_passed_is_styled(qapp, qtbot):
    one, two = QCheckBox("One"), QCheckBox("Two")
    qtbot.addWidget(one)
    qtbot.addWidget(two)
    apply_checkboxes(one, two)
    for box in (one, two):
        assert box.findChildren(LargeIndicatorStyle)


def test_each_box_gets_its_own_style_parented_to_it(qapp, qtbot):
    """Parenting is what keeps the style alive: `setStyle()` does not take
    ownership, and a style collected under a live widget crashes it.

    Asked of the box's *children* rather than of `box.style()`, deliberately.
    Once any ancestor carries a stylesheet Qt slips its own `QStyleSheetStyle`
    in front, so `style()` hands back that proxy rather than this one — the
    metric still comes through it, but the object does not. A check that
    reads `style()` passes on a bare box and fails inside a real window.
    """
    one, two = QCheckBox("One"), QCheckBox("Two")
    qtbot.addWidget(one)
    qtbot.addWidget(two)
    apply_checkboxes(one, two)
    first, second = one.findChildren(LargeIndicatorStyle), two.findChildren(
        LargeIndicatorStyle
    )
    assert len(first) == len(second) == 1
    assert first[0] is not second[0]


def test_the_box_reports_the_bigger_indicator(qapp, qtbot):
    """The point of the exercise, asked of the widget rather than the style."""
    box = QCheckBox("One")
    qtbot.addWidget(box)
    before = box.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
    apply_checkboxes(box)
    after = box.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
    assert after == before * CHECKBOX_SCALE


def test_a_scale_reaches_the_box(qapp, qtbot):
    box = QCheckBox("One")
    qtbot.addWidget(box)
    before = box.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
    apply_checkboxes(box, scale=3)
    after = box.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
    assert after == before * 3


def test_the_box_is_still_a_check_box(qapp, qtbot):
    """Only the drawing changes; the tick and the state are Qt's own."""
    box = QCheckBox("One")
    qtbot.addWidget(box)
    apply_checkboxes(box)
    box.setChecked(True)
    assert box.isChecked()
    box.toggle()
    assert not box.isChecked()
