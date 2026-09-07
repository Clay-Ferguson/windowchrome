"""An on/off switch, shaped like the one a phone's settings screen draws.

Independent of the title bar, like the scroll bars and the radio buttons: no
setup, no platform requirement, and nothing to call before or after the
QApplication. A host constructs one where it would have put a QCheckBox.

Why this is a painted widget and not a styled QCheckBox. The other two
helpers here are stylesheets, because what was wrong with the native widget
was its *size and color*. Here the shape itself is wrong: a check box
indicator is a square with a tick in it, and a stylesheet cannot move a knob
from one end of a track to the other. Qt's own answer would be a pair of
images swapped on toggle, which pins the colors into files and defeats the
point. A checkable QAbstractButton with its own `paintEvent` is a dozen
lines and follows whatever colors it is handed.

What is kept from QCheckBox: it *is* a QAbstractButton, so `isChecked()`,
`setChecked()`, `toggle()`, the `toggled` / `clicked` signals, Space to
flip it and the focus/tab behavior are all the inherited ones. Only the
painting is ours.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPalette
from PyQt6.QtWidgets import QAbstractButton, QApplication, QWidget

# The drawn size of the whole switch, in pixels. Wide enough that the knob
# visibly travels — the movement is what says "this is a switch and not a
# lamp" — and no taller than the label sitting beside it.
TOGGLE_WIDTH = 40
TOGGLE_HEIGHT = 22

# How much track shows around the knob. Also, therefore, how far the knob
# sits from each end: the same gap on all four sides keeps it centered.
TOGGLE_KNOB_MARGIN = 2

# The off track. A mid gray reads as "inactive" against both a dark pane and
# a light one, which no palette role reliably does — `Window` is the title
# bar's under `install()`, and `Base` is the pane the switch sits on, so a
# switch painted in it would disappear.
TOGGLE_OFF_COLOR = "#888888"

# The knob, on both states. White is what makes the off state legible as a
# switch at this size rather than as a gray pill.
TOGGLE_KNOB_COLOR = "#ffffff"


class ToggleSwitch(QAbstractButton):
    """A checkable button painted as a track with a sliding knob.

    `on_color` is the track while checked, and is the one color worth
    passing: it is the host's accent, and defaults to the palette's
    `Highlight` when omitted. `off_color` and `knob_color` are the pinned
    grays above, overridable for a host whose design needs something else.

    Colors are accepted as anything `QColor` takes — a `QColor`, or a name
    or `#rrggbb` string, since a host's accent is usually already a string
    constant.

    The size is fixed rather than laid out: a switch has one drawn shape,
    and a layout that stretched it would stretch the track without moving
    the knob's travel with it.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_color: QColor | str | None = None,
        off_color: QColor | str = TOGGLE_OFF_COLOR,
        knob_color: QColor | str = TOGGLE_KNOB_COLOR,
        width: int = TOGGLE_WIDTH,
        height: int = TOGGLE_HEIGHT,
    ) -> None:
        super().__init__(parent)
        if on_color is None:
            on_color = QApplication.palette().color(QPalette.ColorRole.Highlight)
        self._on_color = QColor(on_color)
        self._off_color = QColor(off_color)
        self._knob_color = QColor(knob_color)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(self._on_color if self.isChecked() else self._off_color)
        radius = self.height() / 2  # a fully rounded pill, whatever the height
        painter.drawRoundedRect(self.rect(), radius, radius)

        diameter = self.height() - 2 * TOGGLE_KNOB_MARGIN
        offset = self.width() - diameter - TOGGLE_KNOB_MARGIN
        knob_x = offset if self.isChecked() else TOGGLE_KNOB_MARGIN
        painter.setBrush(self._knob_color)
        painter.drawEllipse(int(knob_x), TOGGLE_KNOB_MARGIN, diameter, diameter)
