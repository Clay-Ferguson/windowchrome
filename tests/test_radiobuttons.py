"""The enlarged radio indicator: size, visibility, and where the sheet lands.

Like the scroll bar tests, these are claims about the stylesheet string and
about which widget it was set on — nothing here is about pixels Qt painted.
"""

from __future__ import annotations

import re

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QRadioButton, QStyle

from windowchrome import (
    RADIO_BORDER_WIDTH,
    RADIO_INDICATOR_SIZE,
    apply_radios,
    radio_style,
)

FIELD = QColor("#3a3a3a")


def rule(sheet, selector):
    """The body of one rule in the sheet, so a test can look inside it."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    assert match, f"no {selector} rule in:\n{sheet}"
    return match.group(1)


def text_color(qapp):
    return QApplication.palette().color(QPalette.ColorRole.Text)


# -- size -------------------------------------------------------------------


def test_the_indicator_is_square_and_the_size_asked_for(qapp):
    body = rule(radio_style(size=30), "QRadioButton::indicator")
    assert "width: 30px" in body
    assert "height: 30px" in body


def test_the_default_is_bigger_than_the_desktop_would_have_drawn(qapp):
    native = QApplication.style().pixelMetric(
        QStyle.PixelMetric.PM_ExclusiveIndicatorWidth
    )
    assert RADIO_INDICATOR_SIZE > native


def test_the_radius_rounds_the_border_box_into_a_circle(qapp):
    """The border sits outside the width, so half of it counts toward the
    radius or the indicator comes out as a rounded square."""
    body = rule(radio_style(), "QRadioButton::indicator")
    radius = int(re.search(r"border-radius: (\d+)px", body).group(1))
    assert radius == RADIO_INDICATOR_SIZE // 2 + RADIO_BORDER_WIDTH


# -- visibility -------------------------------------------------------------


def test_the_ring_is_drawn_in_the_palettes_text_color(qapp):
    """Not the near-black the native indicator uses, which vanishes on dark."""
    body = rule(radio_style(), "QRadioButton::indicator")
    assert f"solid {text_color(qapp).name()}" in body


def test_checked_fills_the_circle_in_that_same_color(qapp):
    body = rule(radio_style(), "QRadioButton::indicator:checked")
    assert text_color(qapp).name() in body


def test_unchecked_is_painted_in_the_base_it_was_given(qapp):
    body = rule(radio_style(FIELD), "QRadioButton::indicator")
    assert FIELD.name() in body


def test_no_base_falls_back_to_the_palette(qapp):
    base = QApplication.palette().color(QPalette.ColorRole.Base)
    assert radio_style() == radio_style(base)


# -- the label --------------------------------------------------------------


def test_a_point_size_reaches_the_label(qapp):
    assert "font-size: 14pt" in rule(radio_style(point_size=14), "QRadioButton")


def test_no_point_size_leaves_the_font_alone(qapp):
    """Omitted means the widget's own font, not a size this library picked."""
    assert "font-size" not in rule(radio_style(), "QRadioButton")


# -- applying it ------------------------------------------------------------


def test_every_button_passed_is_styled(qapp, qtbot):
    one, two = QRadioButton("One"), QRadioButton("Two")
    qtbot.addWidget(one)
    qtbot.addWidget(two)
    apply_radios(one, two, base=FIELD, point_size=12)
    assert one.styleSheet() == two.styleSheet() == radio_style(FIELD, 12)
