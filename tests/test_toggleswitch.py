"""The on/off switch: the button it still is, and the knob it draws.

Unlike the scroll bar and radio tests, there is no stylesheet string to
inspect here — the widget paints itself. So these ask two kinds of
question: does it still behave like the checkable button it inherits from,
and does what it painted differ between the two states. The second is
answered by rendering the widget into a QImage and reading pixels back,
which is the only place in this suite that looks at actual paint.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QImage, QPainter, QPalette
from PyQt6.QtWidgets import QApplication

from windowchrome import (
    TOGGLE_HEIGHT,
    TOGGLE_KNOB_COLOR,
    TOGGLE_OFF_COLOR,
    TOGGLE_WIDTH,
    ToggleSwitch,
)

ACCENT = "#9e4b2e"


def rendered(switch):
    """The switch painted onto white, as a QImage to sample."""
    image = QImage(switch.size(), QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    switch.render(painter)
    painter.end()
    return image


def track_color(switch):
    """The color at the end of the track the knob is *not* sitting at."""
    image = rendered(switch)
    x = 3 if switch.isChecked() else switch.width() - 4
    return QColor(image.pixel(x, switch.height() // 2))


def knob_center(switch):
    """Where the knob's center is horizontally, found by scanning for it."""
    image = rendered(switch)
    y = switch.height() // 2
    knob = QColor(TOGGLE_KNOB_COLOR).rgb()
    xs = [x for x in range(switch.width()) if image.pixel(x, y) == knob]
    assert xs, "no knob-colored pixels across the middle of the switch"
    return sum(xs) / len(xs)


# -- the button underneath --------------------------------------------------


def test_it_is_checkable_and_starts_off(qapp, qtbot):
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    assert switch.isCheckable()
    assert not switch.isChecked()


def test_toggling_emits_the_inherited_signal(qapp, qtbot):
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    with qtbot.waitSignal(switch.toggled) as blocker:
        switch.setChecked(True)
    assert blocker.args == [True]


def test_it_has_the_drawn_size_and_does_not_stretch(qapp, qtbot):
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    assert switch.size().width() == TOGGLE_WIDTH
    assert switch.size().height() == TOGGLE_HEIGHT
    assert switch.minimumSize() == switch.maximumSize()


def test_the_size_can_be_asked_for(qapp, qtbot):
    switch = ToggleSwitch(width=60, height=30)
    qtbot.addWidget(switch)
    assert (switch.width(), switch.height()) == (60, 30)


# -- what it paints ---------------------------------------------------------


def test_the_knob_travels_when_it_is_switched_on(qapp, qtbot):
    """The movement is the whole point: a switch that only changed color
    would be a lamp."""
    switch = ToggleSwitch(on_color=ACCENT)
    qtbot.addWidget(switch)
    off = knob_center(switch)
    switch.setChecked(True)
    assert knob_center(switch) > off


def test_the_off_track_is_the_gray_and_the_on_track_the_accent(qapp, qtbot):
    switch = ToggleSwitch(on_color=ACCENT)
    qtbot.addWidget(switch)
    assert track_color(switch) == QColor(TOGGLE_OFF_COLOR)
    switch.setChecked(True)
    assert track_color(switch) == QColor(ACCENT)


def test_no_on_color_falls_back_to_the_palettes_highlight(qapp, qtbot):
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    switch.setChecked(True)
    highlight = QApplication.palette().color(QPalette.ColorRole.Highlight)
    assert track_color(switch) == highlight


def test_the_grays_are_overridable(qapp, qtbot):
    switch = ToggleSwitch(off_color="#112233")
    qtbot.addWidget(switch)
    assert track_color(switch) == QColor("#112233")
