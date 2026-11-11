"""The window frame: hit-testing, layout, buttons, colors and the resize filter.

What cannot be tested here is the part the compositor does: under
`QT_QPA_PLATFORM=offscreen` nothing moves or resizes a window, so
`startSystemMove()`/`startSystemResize()` are only checked for being *called*
with the right edges. Dragging, resizing and snapping have to be tried by
hand on a real desktop.

Everything that is decided before the compositor gets involved — which edge
a point is on, where the frame puts the app's layout, which buttons there
are and what they do, what gets painted in which state — is checked here.
Windows go through the `shown` fixture: a window never shown has no layout,
and every geometry assertion below would pass on zeros.
"""

from __future__ import annotations

import gc
import weakref

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from windowchrome import (
    FRAME_BORDER_WIDTH,
    RESIZE_GRAB_WIDTH,
    TITLE_LINE_WIDTH,
    CaptionButton,
    FrameColors,
    apply_frame,
    edge_cursor,
    resize_edges,
)

B = FRAME_BORDER_WIDTH
NONE = Qt.Edge(0)
L, R, T, D = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
SIZE = QSize(400, 300)


def framed(shown, window=None, **kwargs):
    """A plain framed QWidget with a layout, shown and laid out."""
    if window is None:
        window = QWidget()
        QVBoxLayout(window).addWidget(QLabel("content"))
    window.setWindowTitle("Framed")
    frame = apply_frame(window, **kwargs)
    shown(window, SIZE.width(), SIZE.height())
    return window, frame


def pixel(widget, x, y):
    return QColor(widget.grab().toImage().pixel(x, y))


class Recorder(QWidget):
    """A child that fills the window and notes every mouse event it is given,
    so a test can tell whether the frame let one through."""

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.events = []

    def event(self, event):
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
        ):
            self.events.append(event.type())
        return super().event(event)


def recorded(shown, window=None):
    """A framed window whose whole content area is a `Recorder`."""
    window = window or QWidget()
    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    recorder = Recorder()
    layout.addWidget(recorder)
    window, frame = framed(shown, window)
    return window, frame, recorder


def mouse(kind, pos, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
    point = QPointF(pos)
    return QMouseEvent(kind, point, point, button, buttons, Qt.KeyboardModifier.NoModifier)


# -- hit-testing ------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "y", "edges"),
    [
        (200, 150, NONE),
        (0, 150, L),
        (RESIZE_GRAB_WIDTH - 1, 150, L),
        (RESIZE_GRAB_WIDTH, 150, NONE),
        (399, 150, R),
        (200, 0, T),
        (200, 299, D),
        (0, 0, L | T),
        (399, 299, R | D),
        (399, 0, R | T),
        (0, 299, L | D),
    ],
)
def test_resize_edges(x, y, edges):
    assert resize_edges(QPoint(x, y), SIZE) == edges


def test_a_corner_reaches_further_along_each_edge_than_the_grab_width():
    """Within the corner length of a corner counts as the corner, not only
    the small square where the two edge zones overlap."""
    assert resize_edges(QPoint(12, 2), SIZE) == L | T
    assert resize_edges(QPoint(2, 12), SIZE) == L | T
    assert resize_edges(QPoint(30, 2), SIZE) == T


@pytest.mark.parametrize(("x", "y"), [(-1, 5), (400, 5), (5, -1), (5, 300)])
def test_a_point_outside_the_window_is_no_edge(x, y):
    assert resize_edges(QPoint(x, y), SIZE) == NONE


@pytest.mark.parametrize(
    ("edges", "shape"),
    [
        (L, Qt.CursorShape.SizeHorCursor),
        (R, Qt.CursorShape.SizeHorCursor),
        (T, Qt.CursorShape.SizeVerCursor),
        (D, Qt.CursorShape.SizeVerCursor),
        (L | T, Qt.CursorShape.SizeFDiagCursor),
        (R | D, Qt.CursorShape.SizeFDiagCursor),
        (R | T, Qt.CursorShape.SizeBDiagCursor),
        (L | D, Qt.CursorShape.SizeBDiagCursor),
    ],
)
def test_edge_cursor(edges, shape):
    assert edge_cursor(edges) == shape


# -- the frame on a window ----------------------------------------------------


def test_the_window_is_made_frameless(qapp, shown):
    window, _ = framed(shown)
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_applying_twice_hands_back_the_same_frame(qapp, shown):
    window, frame = framed(shown)
    assert apply_frame(window) is frame


def test_the_layout_sits_below_the_title_bar_and_inside_the_border(qapp, shown):
    window, frame = framed(shown)
    height = frame.title_bar.height()
    margins = window.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        B,
        B + height,
        B,
        B,
    )
    assert frame.title_bar.geometry().topLeft() == QPoint(B, B)
    assert frame.title_bar.width() == window.width() - 2 * B
    assert window.findChild(QLabel).geometry().top() >= B + height


def test_a_main_windows_menu_bar_lands_below_the_title_bar(qapp, shown):
    window = QMainWindow()
    window.menuBar().addMenu("&Edit")
    window.setCentralWidget(QLabel("content"))
    window, frame = framed(shown, window)
    assert window.menuBar().geometry().top() == B + frame.title_bar.height()
    assert window.menuBar().geometry().left() == B


def test_a_layouts_own_menu_bar_lands_below_the_title_bar(qapp, shown):
    """Start Menu's shape: a QWidget whose layout holds the menu bar."""
    window = QWidget()
    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    bar = QMenuBar(window)
    bar.addMenu("&Edit")
    layout.setMenuBar(bar)
    layout.addWidget(QLabel("content"))
    window, frame = framed(shown, window)
    assert bar.geometry().top() == B + frame.title_bar.height()


def test_maximized_drops_the_border_and_keeps_the_title_bar(qapp, shown):
    window, frame = framed(shown)
    window.showMaximized()
    margins = window.contentsMargins()
    assert (margins.left(), margins.top()) == (0, frame.title_bar.height())
    assert not frame.border.isVisible()
    assert frame.title_bar.isVisible()
    assert frame.resizable_edges() == NONE


def test_fullscreen_drops_the_title_bar_too(qapp, shown):
    window, frame = framed(shown)
    window.showFullScreen()
    margins = window.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    assert not frame.title_bar.isVisible()


def test_restoring_brings_the_frame_back(qapp, shown):
    window, frame = framed(shown)
    window.showMaximized()
    window.showNormal()
    assert window.contentsMargins().left() == B
    assert frame.border.isVisible()


# -- buttons ----------------------------------------------------------------


def kinds(frame):
    return [button.kind for button in frame.title_bar.buttons]


def test_a_window_gets_all_three_buttons_close_last(qapp, shown):
    _, frame = framed(shown)
    assert kinds(frame) == [CaptionButton.MINIMIZE, CaptionButton.MAXIMIZE, CaptionButton.CLOSE]
    assert frame.title_bar.close_button.geometry().right() == frame.title_bar.width() - 1


def test_a_dialog_gets_only_a_close_button(qapp, shown):
    _, frame = framed(shown, QDialog())
    assert kinds(frame) == [CaptionButton.CLOSE]


def test_a_dialog_can_ask_for_more(qapp, shown):
    _, frame = framed(shown, QDialog(), maximize=True)
    assert kinds(frame) == [CaptionButton.MAXIMIZE, CaptionButton.CLOSE]


def test_maximize_toggles_and_its_glyph_follows(qapp, shown, qtbot):
    window, frame = framed(shown)
    button = frame.title_bar.maximize_button
    before = button.grab().toImage()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert window.isMaximized()
    assert button.grab().toImage() != before  # the restore glyph
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert not window.isMaximized()


def test_close_closes(qapp, shown, qtbot):
    window, frame = framed(shown)
    qtbot.mouseClick(frame.title_bar.close_button, Qt.MouseButton.LeftButton)
    assert not window.isVisible()


def test_minimize_minimizes(qapp, shown, qtbot):
    window, frame = framed(shown)
    qtbot.mouseClick(frame.title_bar.minimize_button, Qt.MouseButton.LeftButton)
    assert window.windowState() & Qt.WindowState.WindowMinimized


def test_double_clicking_the_bar_toggles_maximize(qapp, shown, qtbot):
    window, frame = framed(shown)
    qtbot.mouseDClick(frame.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(60, 15))
    assert window.isMaximized()
    qtbot.mouseDClick(frame.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(60, 15))
    assert not window.isMaximized()


def test_double_clicking_a_dialogs_bar_does_nothing(qapp, shown, qtbot):
    window, frame = framed(shown, QDialog())
    qtbot.mouseDClick(frame.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(60, 15))
    assert not window.isMaximized()


def test_the_buttons_never_take_focus(qapp, shown):
    _, frame = framed(shown)
    for button in frame.title_bar.buttons:
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_button_fills(qapp, shown):
    _, frame = framed(shown)
    colors = frame.colors
    close = frame.title_bar.close_button
    minimize = frame.title_bar.minimize_button
    assert close.background() is None  # at rest, the bar shows through
    close.setDown(True)
    minimize.setDown(True)
    assert close.background() == QColor(colors.close_pressed)
    assert minimize.background() == QColor(colors.button_pressed)


# -- the title ----------------------------------------------------------------


def test_the_title_follows_set_window_title(qapp, shown):
    window, frame = framed(shown)
    window.setWindowTitle("Something else")
    assert frame.title_bar.displayed_title() == "Something else"


def test_a_long_title_is_elided_to_fit(qapp, shown):
    window, frame = framed(shown)
    window.setWindowTitle("A title far too long to fit " * 10)
    shown_title = frame.title_bar.displayed_title()
    assert shown_title.endswith("…")
    width = frame.title_bar.fontMetrics().horizontalAdvance(shown_title)
    assert width <= frame.title_bar.title_rect().width()


def test_the_title_space_stops_at_the_buttons(qapp, shown):
    _, frame = framed(shown)
    first_button = frame.title_bar.buttons[0]
    assert frame.title_bar.title_rect().right() < first_button.geometry().left()


# -- colors -------------------------------------------------------------------


def test_active_colors(qapp, shown, qtbot):
    window, frame = framed(shown)
    qtbot.waitUntil(window.isActiveWindow)
    bar = frame.title_bar
    colors = frame.colors
    assert pixel(window, B + 4, B + 4) == QColor(colors.title_bg)
    assert pixel(window, B + 4, B + bar.height() - 1) == QColor(colors.title_line)
    assert pixel(window, B + 4, B + bar.height() - TITLE_LINE_WIDTH) == QColor(colors.title_line)
    assert pixel(window, B + 4, B + bar.height() - TITLE_LINE_WIDTH - 1) == QColor(colors.title_bg)


def test_inactive_colors(qapp, shown, qtbot):
    window, frame = framed(shown)
    other = QWidget()
    shown(other)
    other.activateWindow()
    qtbot.waitUntil(lambda: not window.isActiveWindow())
    colors = frame.colors
    assert pixel(window, B + 4, B + 4) == QColor(colors.inactive_title_bg)
    assert pixel(window, B + 4, B + frame.title_bar.height() - 1) == QColor(
        colors.inactive_title_line
    )


@pytest.mark.parametrize(("x", "y"), [(0, 150), (1, 150), (399, 150), (200, 299), (0, 0)])
def test_the_border_is_drawn_all_round(qapp, shown, x, y):
    window, frame = framed(shown)
    assert pixel(window, x, y) == QColor(frame.colors.border)


def test_colors_can_be_overridden(qapp, shown, qtbot):
    window, _ = framed(shown, colors=FrameColors(title_bg="#ff0000", border="#00ff00"))
    qtbot.waitUntil(window.isActiveWindow)
    assert pixel(window, B + 4, B + 4) == QColor("#ff0000")
    assert pixel(window, 0, 150) == QColor("#00ff00")


def test_set_colors_repaints(qapp, shown, qtbot):
    window, frame = framed(shown)
    qtbot.waitUntil(window.isActiveWindow)
    frame.set_colors(FrameColors(title_bg="#0000ff"))
    assert pixel(window, B + 4, B + 4) == QColor("#0000ff")


def test_the_frame_does_not_keep_its_window_alive(qapp):
    """Nothing in the frame may hold a reference back to the window.

    One that did put the window in a reference cycle, so it was freed
    whenever the cycle collector next ran rather than when the last
    reference went — which, measured, was in the middle of painting the
    title bar, and crashed. With the collector off, the window has to go
    the moment it is dropped.
    """
    gc.disable()
    try:
        window = QWidget()
        apply_frame(window)
        alive = weakref.ref(window)
        del window
        assert alive() is None
    finally:
        gc.enable()


def test_nothing_application_wide_is_touched(qapp, shown):
    palette = QApplication.palette()
    sheet = qapp.styleSheet()
    framed(shown)
    assert QApplication.palette() == palette
    assert qapp.styleSheet() == sheet


# -- the resize filter ----------------------------------------------------------


PRESS = {"button": Qt.MouseButton.LeftButton, "buttons": Qt.MouseButton.LeftButton}


def send(window, kind, pos, **kwargs):
    """Deliver a mouse event to the window's QWindow, as the platform would."""
    QApplication.sendEvent(window.windowHandle(), mouse(kind, pos, **kwargs))


def cursor(window):
    return window.windowHandle().cursor().shape()


def test_the_edge_shows_a_resize_cursor_and_the_middle_gives_it_back(qapp, shown):
    window, _, _ = recorded(shown)
    send(window, QEvent.Type.MouseMove, QPoint(B + 2, 150))
    assert cursor(window) == Qt.CursorShape.SizeHorCursor
    send(window, QEvent.Type.MouseMove, QPoint(200, 150))
    assert cursor(window) == Qt.CursorShape.ArrowCursor


def test_the_zone_reaches_over_a_child_widget(qapp, shown):
    """The point of filtering the QWindow: a child at the edge neither hides
    the zone nor sees the events the zone takes."""
    window, _, recorder = recorded(shown)
    pos = QPoint(B + 2, 150)
    assert window.childAt(pos) is recorder
    send(window, QEvent.Type.MouseMove, pos)
    assert recorder.events == []
    send(window, QEvent.Type.MouseMove, QPoint(200, 150))
    assert recorder.events == [QEvent.Type.MouseMove]


def test_a_press_on_an_edge_starts_a_system_resize(qapp, shown, monkeypatch):
    window, _, recorder = recorded(shown)
    calls = []
    monkeypatch.setattr(window.windowHandle(), "startSystemResize", calls.append)
    send(window, QEvent.Type.MouseButtonPress, QPoint(399, 299), **PRESS)
    send(window, QEvent.Type.MouseButtonRelease, QPoint(399, 299), **PRESS)
    assert calls == [R | D]
    # The press and the release that ends the resize both stop at the frame.
    assert recorder.events == []


def test_a_press_in_the_middle_is_left_alone(qapp, shown, monkeypatch):
    window, _, recorder = recorded(shown)
    calls = []
    monkeypatch.setattr(window.windowHandle(), "startSystemResize", calls.append)
    send(window, QEvent.Type.MouseButtonPress, QPoint(200, 150), **PRESS)
    assert calls == []
    assert recorder.events == [QEvent.Type.MouseButtonPress]


def test_no_resize_zones_while_maximized(qapp, shown):
    window, _, recorder = recorded(shown)
    window.showMaximized()
    send(window, QEvent.Type.MouseMove, QPoint(B + 2, 150))
    assert cursor(window) == Qt.CursorShape.ArrowCursor
    assert recorder.events == [QEvent.Type.MouseMove]


def test_a_fixed_size_window_offers_no_resize(qapp, shown):
    window = QWidget()
    window.setFixedSize(SIZE)
    window, frame, _ = recorded(shown, window)
    assert frame.resizable_edges() == NONE
    send(window, QEvent.Type.MouseMove, QPoint(B + 2, 150))
    assert cursor(window) == Qt.CursorShape.ArrowCursor


def test_a_window_fixed_in_one_axis_resizes_in_the_other(qapp, shown):
    window = QWidget()
    window.setFixedWidth(SIZE.width())
    window, frame = framed(shown, window)
    assert frame.resizable_edges() == T | D


def test_a_message_box_can_be_framed(qapp, qtbot):
    """QMessageBox sizes itself on show; the frame's margins have to be in it."""
    box = QMessageBox(QMessageBox.Icon.Information, "A title", "Some text to show.")
    qtbot.addWidget(box)
    frame = apply_frame(box)
    box.show()
    qtbot.waitExposed(box)
    label = box.findChild(QLabel, "qt_msgbox_label")
    assert label.geometry().top() >= B + frame.title_bar.height()
    assert label.geometry().bottom() < box.height() - B
