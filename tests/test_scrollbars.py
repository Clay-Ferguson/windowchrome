"""The wide scroll bars: thickness, steppers, and which way the contrast goes.

None of this is about pixels — the stylesheet is a string, and every claim
worth making about it is a claim about what that string says, or about which
widget it was set on.
"""

from __future__ import annotations

import re

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPlainTextEdit

from windowchrome import (
    MIN_SCROLLBAR_EXTENT,
    SCROLLBAR_SCALE,
    apply_scrollbars,
    scrollbar_style,
)

DARK = QColor("#1e1e1e")
LIGHT = QColor("#ffffff")

FLOOR = MIN_SCROLLBAR_EXTENT * SCROLLBAR_SCALE


def rule(sheet, selector):
    """The body of one rule in the sheet, so a test can look inside it."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    assert match, f"no {selector} rule in:\n{sheet}"
    return match.group(1)


def colors(sheet):
    """Every color the sheet names, in the order it names them."""
    return [QColor(hexcode) for hexcode in re.findall(r"#[0-9a-fA-F]{6}", sheet)]


# -- thickness --------------------------------------------------------------


def test_vertical_bar_is_at_least_the_doubled_floor(qapp):
    width = int(re.search(r"width: (\d+)px", rule(scrollbar_style(), "QScrollBar:vertical")).group(1))
    assert width >= FLOOR


def test_horizontal_bar_matches_the_vertical_one(qapp):
    sheet = scrollbar_style()
    width = re.search(r"width: (\d+)px", rule(sheet, "QScrollBar:vertical")).group(1)
    height = re.search(r"height: (\d+)px", rule(sheet, "QScrollBar:horizontal")).group(1)
    assert width == height


def test_the_bar_is_wider_than_the_desktop_would_have_drawn(qapp):
    from PyQt6.QtWidgets import QApplication, QStyle

    extent = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
    width = int(re.search(r"width: (\d+)px", rule(scrollbar_style(), "QScrollBar:vertical")).group(1))
    assert width > extent


# -- steppers ---------------------------------------------------------------


def test_steppers_are_collapsed_to_nothing(qapp):
    """Left undescribed they render as blank boxes at each end of the bar."""
    body = rule(scrollbar_style(), "QScrollBar::add-line, QScrollBar::sub-line")
    assert "width: 0" in body
    assert "height: 0" in body
    assert "background: none" in body


# -- light and dark ---------------------------------------------------------


@pytest.mark.parametrize("base", [DARK, LIGHT])
def test_the_groove_is_painted_in_the_base_it_was_given(qapp, base):
    assert colors(scrollbar_style(base))[0] == base


@pytest.mark.parametrize("base", [DARK, LIGHT])
def test_the_handle_contrasts_with_its_own_groove(qapp, base):
    handle = QColor(rule(scrollbar_style(base), "QScrollBar::handle").split("background:")[1].split(";")[0].strip())
    assert abs(handle.lightness() - base.lightness()) > 20


def test_a_dark_theme_and_a_light_one_do_not_get_the_same_handle(qapp):
    assert scrollbar_style(DARK) != scrollbar_style(LIGHT)


def test_the_handle_lightens_on_dark_and_darkens_on_light(qapp):
    def handle(base):
        body = rule(scrollbar_style(base), "QScrollBar::handle")
        return QColor(body.split("background:")[1].split(";")[0].strip())

    assert handle(DARK).lightness() > DARK.lightness()
    assert handle(LIGHT).lightness() < LIGHT.lightness()


def test_no_base_falls_back_to_the_palette(qapp):
    from PyQt6.QtGui import QPalette
    from PyQt6.QtWidgets import QApplication

    base = QApplication.palette().color(QPalette.ColorRole.Base)
    assert scrollbar_style() == scrollbar_style(base)


# -- applying it ------------------------------------------------------------


def test_both_bars_are_styled(qapp, qtbot):
    edit = QPlainTextEdit()
    qtbot.addWidget(edit)
    apply_scrollbars(edit)
    assert "QScrollBar" in edit.verticalScrollBar().styleSheet()
    assert "QScrollBar" in edit.horizontalScrollBar().styleSheet()


def test_the_area_itself_is_left_alone(qapp, qtbot):
    """The stylesheet goes on the bars so the widget keeps native rendering."""
    edit = QPlainTextEdit()
    qtbot.addWidget(edit)
    edit.setStyleSheet("background-color: #123456;")
    apply_scrollbars(edit)
    assert edit.styleSheet() == "background-color: #123456;"


def test_the_base_reaches_the_bars(qapp, qtbot):
    edit = QPlainTextEdit()
    qtbot.addWidget(edit)
    apply_scrollbars(edit, DARK)
    assert edit.verticalScrollBar().styleSheet() == scrollbar_style(DARK)
