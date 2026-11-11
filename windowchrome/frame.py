"""A title bar and window frame drawn by the application itself.

One call per top-level window, before it is first shown:

    apply_frame(window)                     # a QWidget, QMainWindow or QDialog
    apply_frame(box)                        # ... or a QMessageBox you built

No setup around the QApplication and nothing application-wide: no palette
or stylesheet change, no event filter on QApplication. Everything here is
attached to the one window it was handed, through documented Qt API only.

How it fits together, and why this shape:

- The window is made frameless (`Qt.WindowType.FramelessWindowHint`), so no
  decoration plugin (`adwaita`, `bradient`) draws anything and nothing here
  depends on how one works inside.
- **The window stays the window.** The frame lives *inside* it, in its
  contents margins: the top margin holds the `TitleBar`, and a
  `FRAME_BORDER_WIDTH` margin on every side holds the border. Qt lays a
  window's layout out inside its contents rectangle, so the app's own
  layout — a QMainWindow's menu bar included — lands below the title bar and
  inside the border without being touched. A wrapper widget around the
  app's content would take the window's identity away from it instead:
  `close()`, `setWindowTitle()`, the window state and, for a QDialog,
  `exec()`/`accept()` all belong to the top-level widget.
- **The border is a child widget, not the window's own painting.** A plain
  widget that paints the ring and nothing else, transparent to the mouse
  and kept at the bottom of the stacking order, so the app's widgets cover
  it everywhere except the margin. Painting it any other way would mean
  subclassing the app's window or changing its palette.
- **The resize zones are an event filter on the window's QWindow.** Every
  mouse event for a top-level window reaches its QWindow before Qt hands it
  to whichever child widget is under the pointer, so a filter there sees the
  edge even where the app's tree view or scroll bar reaches it — which a
  filter on the frame's own widgets never would. It is scoped to this one
  window, unlike a filter on QApplication. The zone is `RESIZE_GRAB_WIDTH`
  from the outer edge, wider than the border because a 2px target is too
  thin to hit; the rest of it is inside the content.

Moving and resizing are the compositor's job: `QWindow.startSystemMove()`
and `startSystemResize()` (both since Qt 5.15) hand it the drag, which on
Wayland is the only way a window can be moved at all, and which keeps edge
snapping and tiling working.

There is no drop shadow, deliberately. Faking one needs a translucent margin
around the drawn window, and Qt has no public API to tell a Wayland
compositor that the margin is not part of the window, so maximizing and
tiling would leave a visible gap. The border is what separates the window
from the desktop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QAbstractButton, QApplication, QDialog, QWidget

# The visible border around the whole window, drawn inside it. GTK draws the
# same 2px as a 1px border plus a 1px box-shadow; here it is one solid ring.
FRAME_BORDER_WIDTH = 2

# How far in from the window's outer edge a press starts a resize. Wider than
# the border, which alone would be a 2px target; the rest of the zone lies
# over the content, as it does on any window whose resize area is inside it.
RESIZE_GRAB_WIDTH = 8

# How far along each edge from a corner the zone resizes diagonally. Longer
# than the grab width, so a corner is a target in its own right rather than
# the 8×8 square where two edge zones happen to overlap.
RESIZE_CORNER_LENGTH = 16

# The line along the title bar's bottom edge, drawn inside the bar (GTK's
# `box-shadow: inset 0 -2px`), not as a strip below it.
TITLE_LINE_WIDTH = 2

# The title bar's height is the title font's line height plus this much, and
# never less than TITLE_BAR_MIN_HEIGHT — sized from the font so a large
# desktop font doesn't crowd the bar.
TITLE_BAR_PADDING = 20
TITLE_BAR_MIN_HEIGHT = 36

# Each caption button is a rectangle the full height of the bar, this wide,
# with its glyph drawn GLYPH_SIZE across in the middle of it.
CAPTION_BUTTON_WIDTH = 46
GLYPH_SIZE = 10

# The gap kept between the title and either end of the space it is centered
# in, so an elided title doesn't run into the buttons.
TITLE_SIDE_PADDING = 12


@dataclass(frozen=True)
class FrameColors:
    """Every color the frame paints, as anything `QColor` accepts.

    The defaults are taken from a GTK theme's CSS, so a Qt window's frame
    matches the GTK apps beside it; the `inactive_` fields are GTK's
    `:backdrop`, the state a window is in while another one has focus.
    Override any of them with `dataclasses.replace(FrameColors(), ...)` or by
    constructing one with keywords.

    The button hover and pressed colors apply in both states. The close
    button's own red is drawn with white glyphs whatever the state, since the
    inactive glyph color would be lost against it.
    """

    title_bg: str = "#1e3a5f"
    title_fg: str = "#ffffff"
    title_line: str = "#2c6dbc"
    inactive_title_bg: str = "#112238"
    inactive_title_fg: str = "#8fa1b8"
    inactive_title_line: str = "#1c3d5a"
    border: str = "#777777"
    button_hover: str = "#2d5282"
    button_pressed: str = "#2c6dbc"
    close_hover: str = "#c01c28"
    close_pressed: str = "#a51d2d"


def resize_edges(
    pos: QPoint,
    size: QSize,
    grab: int = RESIZE_GRAB_WIDTH,
    corner: int = RESIZE_CORNER_LENGTH,
) -> Qt.Edge:
    """Which edges a press at `pos` would resize, in a window of `size`.

    `Qt.Edge(0)` — falsy — away from every edge, and for a point outside the
    window. Near a corner both of its edges come back: within `corner` of one
    end of an edge zone counts as that corner, not only the overlap square.

    Pure geometry, so it is the part of the resize handling a test can reach
    without a compositor.
    """
    x, y, width, height = pos.x(), pos.y(), size.width(), size.height()
    if not (0 <= x < width and 0 <= y < height):
        return Qt.Edge(0)

    near_left, near_right = x < corner, x >= width - corner
    near_top, near_bottom = y < corner, y >= height - corner
    edges = Qt.Edge(0)
    if x < grab or (near_left and (y < grab or y >= height - grab)):
        edges |= Qt.Edge.LeftEdge
    if x >= width - grab or (near_right and (y < grab or y >= height - grab)):
        edges |= Qt.Edge.RightEdge
    if y < grab or (near_top and (x < grab or x >= width - grab)):
        edges |= Qt.Edge.TopEdge
    if y >= height - grab or (near_bottom and (x < grab or x >= width - grab)):
        edges |= Qt.Edge.BottomEdge
    return edges


def edge_cursor(edges: Qt.Edge) -> Qt.CursorShape:
    """The resize cursor for a set of edges from `resize_edges()`."""
    left, right = bool(edges & Qt.Edge.LeftEdge), bool(edges & Qt.Edge.RightEdge)
    top, bottom = bool(edges & Qt.Edge.TopEdge), bool(edges & Qt.Edge.BottomEdge)
    if (left and top) or (right and bottom):
        return Qt.CursorShape.SizeFDiagCursor
    if (right and top) or (left and bottom):
        return Qt.CursorShape.SizeBDiagCursor
    if left or right:
        return Qt.CursorShape.SizeHorCursor
    return Qt.CursorShape.SizeVerCursor


class CaptionButton(QAbstractButton):
    """One of the title bar's minimize, maximize and close buttons.

    The glyphs are painted rather than taken from the icon theme. Yaru ships
    only a close icon; Adwaita ships all four, but only as dark symbolic SVGs,
    which need Qt's SVG plugin to load at all and would then have to be
    recolored for this bar, for the inactive state and for the close
    button's hover. Each glyph here is one to four strokes in whatever color
    the state calls for, sharp at any scale factor, with no files.

    Never takes focus: clicking one must leave the keyboard where it was.
    """

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    CLOSE = "close"

    def __init__(self, kind: str, title_bar: TitleBar) -> None:
        super().__init__(title_bar)
        self.kind = kind
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Repaint on entering and leaving, which a hover color needs.
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setToolTip(
            {"minimize": "Minimize", "maximize": "Maximize", "close": "Close"}[kind]
        )

    @property
    def _title_bar(self) -> TitleBar:
        return cast(TitleBar, self.parentWidget())

    def background(self) -> QColor | None:
        """The fill for the current mouse state, or None to show the bar."""
        colors = self._title_bar.colors
        if self.kind == self.CLOSE:
            pressed, hover = colors.close_pressed, colors.close_hover
        else:
            pressed, hover = colors.button_pressed, colors.button_hover
        if self.isDown():
            return QColor(pressed)
        if self.underMouse():
            return QColor(hover)
        return None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        fill = self.background()
        if fill is not None:
            # Stop short of the bar's bottom line, which runs under the buttons.
            painter.fillRect(self.rect().adjusted(0, 0, 0, -TITLE_LINE_WIDTH), fill)

        if self.kind == self.CLOSE and fill is not None:
            glyph = QColor("#ffffff")
        else:
            glyph = self._title_bar.foreground()
        pen = QPen(glyph)
        pen.setWidthF(1.0)
        painter.setPen(pen)

        # The glyph spans x..x+s and y..y+s, centered above the bottom line.
        # Drawn unantialiased with a 1px pen: horizontals, verticals and the
        # close button's exact 45° diagonals all land on whole pixels, and
        # antialiasing only turns them gray.
        s = GLYPH_SIZE
        x = (self.width() - s) // 2
        y = (self.height() - TITLE_LINE_WIDTH - s) // 2
        if self.kind == self.MINIMIZE:
            painter.drawLine(x, y + s // 2, x + s, y + s // 2)
        elif self.kind == self.MAXIMIZE:
            if self._title_bar.window().isMaximized():
                # Restore: a smaller window, and the corner of one behind it.
                o = 3
                painter.drawRect(QRect(x, y + o, s - o, s - o))
                painter.drawPolyline(
                    QPolygon(
                        [
                            QPoint(x + o, y + o),
                            QPoint(x + o, y),
                            QPoint(x + s, y),
                            QPoint(x + s, y + s - o),
                            QPoint(x + s - o, y + s - o),
                        ]
                    )
                )
            else:
                painter.drawRect(QRect(x, y, s, s))
        else:
            painter.drawLine(x, y, x + s, y + s)
            painter.drawLine(x + s, y, x, y + s)


class TitleBar(QWidget):
    """The bar along the top of a framed window: title, then the buttons.

    A child of the window it heads, placed in the window's top contents
    margin by `WindowFrame`; it is never in the app's layout.

    Dragging it moves the window, but only once the mouse has moved the
    desktop's drag distance. Starting the move on the press itself would hand
    the pointer to the compositor before a second click could arrive, and
    double-click-to-maximize would be unreliable — GTK waits for the same
    threshold. On Wayland the compositor accepts the move because the button
    is still held from the press it is answering.
    """

    def __init__(
        self, window: QWidget, colors: FrameColors, *, minimize: bool, maximize: bool
    ) -> None:
        super().__init__(window)
        self.colors = colors
        self._press_pos: QPoint | None = None

        font = QFont(self.font())
        font.setBold(True)
        self.setFont(font)
        self.setFixedHeight(
            max(TITLE_BAR_MIN_HEIGHT, self.fontMetrics().height() + TITLE_BAR_PADDING)
        )

        self.buttons: list[CaptionButton] = []
        if minimize:
            self.minimize_button = self._add_button(
                CaptionButton.MINIMIZE, self.minimize
            )
        if maximize:
            self.maximize_button = self._add_button(
                CaptionButton.MAXIMIZE, self.toggle_maximized
            )
        self.close_button = self._add_button(CaptionButton.CLOSE, self.close_window)
        self._maximizable = maximize

        window.windowTitleChanged.connect(self.update)

    def _add_button(self, kind: str, slot) -> CaptionButton:
        button = CaptionButton(kind, self)
        button.clicked.connect(slot)
        self.buttons.append(button)
        return button

    def is_active(self) -> bool:
        return self.window().isActiveWindow()

    def background(self) -> QColor:
        return QColor(
            self.colors.title_bg if self.is_active() else self.colors.inactive_title_bg
        )

    def foreground(self) -> QColor:
        return QColor(
            self.colors.title_fg if self.is_active() else self.colors.inactive_title_fg
        )

    def line(self) -> QColor:
        return QColor(
            self.colors.title_line
            if self.is_active()
            else self.colors.inactive_title_line
        )

    # The buttons are connected to these rather than to the window's own
    # slots: a connection to `window.close` would hold a reference to the
    # window from inside it, and a window caught in a reference cycle is freed
    # whenever Python's cycle collector happens to run — measured, in the
    # middle of painting this bar, which crashed.

    def minimize(self) -> None:
        self.window().showMinimized()

    def close_window(self) -> None:
        self.window().close()

    def toggle_maximized(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    def title_rect(self) -> QRect:
        """The space the title is centered in: everything left of the buttons."""
        buttons_left = self.width() - len(self.buttons) * CAPTION_BUTTON_WIDTH
        return QRect(
            TITLE_SIDE_PADDING,
            0,
            max(0, buttons_left - 2 * TITLE_SIDE_PADDING),
            self.height() - TITLE_LINE_WIDTH,
        )

    def displayed_title(self) -> str:
        """The window's title as drawn: elided to fit `title_rect()`."""
        return self.fontMetrics().elidedText(
            self.window().windowTitle(),
            Qt.TextElideMode.ElideRight,
            self.title_rect().width(),
        )

    def resizeEvent(self, event) -> None:
        x = self.width()
        for button in reversed(self.buttons):
            x -= CAPTION_BUTTON_WIDTH
            button.setGeometry(x, 0, CAPTION_BUTTON_WIDTH, self.height())
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background())
        painter.fillRect(
            0,
            self.height() - TITLE_LINE_WIDTH,
            self.width(),
            TITLE_LINE_WIDTH,
            self.line(),
        )
        painter.setPen(self.foreground())
        painter.drawText(
            self.title_rect(), Qt.AlignmentFlag.AlignCenter, self.displayed_title()
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            moved = event.position().toPoint() - self._press_pos
            if moved.manhattanLength() >= QApplication.startDragDistance():
                self._press_pos = None
                handle = self.window().windowHandle()
                if handle is not None:
                    handle.startSystemMove()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._maximizable:
            self._press_pos = None
            self.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class _Border(QWidget):
    """The ring around the window: a full-window child that paints only its
    outer `FRAME_BORDER_WIDTH` pixels, invisible to the mouse and kept below
    every other child."""

    def __init__(self, window: QWidget, color: str) -> None:
        super().__init__(window)
        self.color = color
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        color = QColor(self.color)
        w, h, b = self.width(), self.height(), FRAME_BORDER_WIDTH
        painter.fillRect(0, 0, w, b, color)
        painter.fillRect(0, h - b, w, b, color)
        painter.fillRect(0, b, b, h - 2 * b, color)
        painter.fillRect(w - b, b, b, h - 2 * b, color)


class WindowFrame(QObject):
    """The frame `apply_frame()` puts on one window, and owns its parts.

    A child of the window, so it lives exactly as long as the window does.
    `title_bar` is public for a host that wants to reach it; `set_colors()`
    repaints with new colors.

    It filters two objects, both belonging to this window alone: the window
    widget (for its size, state, activation and first show) and the window's
    QWindow (for the resize zones; see the module docstring).
    """

    def __init__(
        self, window: QWidget, colors: FrameColors, *, minimize: bool, maximize: bool
    ) -> None:
        super().__init__(window)
        self._handle = None
        self._over_edge = False
        self._resizing = False

        was_visible = window.isVisible()
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.border = _Border(window, colors.border)
        self.border.lower()
        self.title_bar = TitleBar(window, colors, minimize=minimize, maximize=maximize)

        window.installEventFilter(self)
        self._update_geometry()
        # Changing the window flags hides a window that was already showing.
        if was_visible:
            window.show()
        self._hook_window()

    @property
    def _window(self) -> QWidget:
        # The parent, looked up rather than stored: a reference held here
        # would put the window in a reference cycle with its own frame (see
        # TitleBar.minimize).
        return cast(QWidget, self.parent())

    @property
    def colors(self) -> FrameColors:
        return self.title_bar.colors

    def set_colors(self, colors: FrameColors) -> None:
        self.title_bar.colors = colors
        self.border.color = colors.border
        self.title_bar.update()
        self.border.update()

    def is_framed(self) -> bool:
        """False while maximized or fullscreen: no border, no resize zones."""
        state = self._window.windowState()
        return not state & (
            Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
        )

    def _update_geometry(self) -> None:
        window = self._window
        fullscreen = bool(window.windowState() & Qt.WindowState.WindowFullScreen)
        border = FRAME_BORDER_WIDTH if self.is_framed() else 0
        title = 0 if fullscreen else self.title_bar.height()

        # The app's layout is laid out inside these margins.
        window.setContentsMargins(border, border + title, border, border)
        self.title_bar.setVisible(not fullscreen)
        self.title_bar.setGeometry(border, border, window.width() - 2 * border, title)
        self.border.setVisible(bool(border))
        self.border.setGeometry(0, 0, window.width(), window.height())
        self.title_bar.update()

    def _hook_window(self) -> None:
        """Filter the window's QWindow, which exists only once it is created."""
        handle = self._window.windowHandle()
        if handle is None or handle is self._handle:
            return
        if self._handle is not None:
            self._handle.removeEventFilter(self)
        self._handle = handle
        handle.installEventFilter(self)

    def resizable_edges(self) -> Qt.Edge:
        """The edges the window can be resized from right now.

        None while maximized or fullscreen, and none along an axis the window
        is fixed in — a QMessageBox fixes its own size, and offering a resize
        cursor it would refuse is worse than offering nothing.
        """
        if not self.is_framed():
            return Qt.Edge(0)
        window = self._window
        edges = Qt.Edge(0)
        if window.minimumWidth() != window.maximumWidth():
            edges |= Qt.Edge.LeftEdge | Qt.Edge.RightEdge
        if window.minimumHeight() != window.maximumHeight():
            edges |= Qt.Edge.TopEdge | Qt.Edge.BottomEdge
        return edges

    def eventFilter(self, obj, event) -> bool:
        if obj is self._window:
            self._window_event(event)
            return False
        if obj is self._handle:
            return self._handle_event(event)
        return False

    def _window_event(self, event) -> None:
        kind = event.type()
        if kind in (QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            self._update_geometry()
        elif kind in (
            QEvent.Type.ActivationChange,
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
        ):
            self.title_bar.update()
        elif kind in (QEvent.Type.Show, QEvent.Type.WinIdChange):
            self._hook_window()

    def _handle_event(self, event) -> bool:
        """The resize zones. True swallows the event before any child sees it."""
        kind = event.type()
        if kind == QEvent.Type.Leave:
            self._over_edge = False
            return False
        if kind == QEvent.Type.MouseButtonRelease and self._resizing:
            # The release that ends a resize belongs to no child: none saw the press.
            self._resizing = False
            return True
        if kind not in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            return False

        pos = event.position().toPoint()
        edges = resize_edges(pos, self._window.size()) & self.resizable_edges()
        if kind == QEvent.Type.MouseMove:
            if event.buttons() != Qt.MouseButton.NoButton:
                return False  # a drag that began inside some child: leave it be
            if edges:
                self._over_edge = True
                self._handle.setCursor(QCursor(edge_cursor(edges)))
                return True
            if self._over_edge:
                # Hand the pointer back to whatever widget is under it. Qt would
                # not do this itself: it never saw the moves that were swallowed.
                self._over_edge = False
                under = self._window.childAt(pos) or self._window
                self._handle.setCursor(under.cursor())
            return False

        if edges and event.button() == Qt.MouseButton.LeftButton:
            self._resizing = True
            self._handle.startSystemResize(edges)
            return True
        return False


def apply_frame(
    window: QWidget,
    colors: FrameColors | None = None,
    *,
    minimize: bool | None = None,
    maximize: bool | None = None,
) -> WindowFrame:
    """Draw this window's own title bar and border, replacing the system's.

    Call it once, before the window is first shown; calling it again hands
    back the frame already there. Returns the `WindowFrame`, which a host
    needs only to change colors later or reach the title bar.

    `minimize` and `maximize` say which of those buttons to show, the close
    button always being there. Both default to on, except on a QDialog
    (QMessageBox included), which has only a close button, as a dialog does
    on GNOME. Without a maximize button, double-clicking the bar does nothing
    either.

    The window's own contents margins become the frame's: a host that sets
    them on the window itself afterwards will be overwritten on the next
    resize. Margins on its *layout* are untouched and still apply.
    """
    existing = window.findChild(
        WindowFrame, options=Qt.FindChildOption.FindDirectChildrenOnly
    )
    if existing is not None:
        return existing
    is_dialog = isinstance(window, QDialog)
    return WindowFrame(
        window,
        colors if colors is not None else FrameColors(),
        minimize=not is_dialog if minimize is None else minimize,
        maximize=not is_dialog if maximize is None else maximize,
    )
