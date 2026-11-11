"""The menu bar and drop-downs: the gray edges, the colors, and what is left alone.

Unlike the scroll bar and radio tests, most of these read pixels: what the
sheet is for is an edge Fusion would otherwise draw near-black, and whether
Qt paints the bar from the stylesheet or hands it to the native style is a
question only the rendered image answers. Pixels are read with
`QImage.pixelColor()` — `QColor(image.pixel())` drops the alpha.
"""

from __future__ import annotations

import gc
import re
import weakref

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QMouseEvent, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QProxyStyle,
    QStyle,
)

from windowchrome import DIVIDER_BORDER, DIVIDER_COLOR, apply_menus, menu_style

GRAY = QColor(DIVIDER_COLOR)
RED = QColor("#ff0000")
GREEN = QColor("#00ff00")
BLUE = QColor("#0000ff")
# The Yaru-dark window color the apps run on. Offscreen Fusion's own palette
# is light, where its line is a soft gray rather than the near-black one.
DARK_WINDOW = "#2c2c2c"


def rule(sheet, selector):
    """The body of one rule in the sheet, so a test can look inside it."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    assert match, f"no {selector} rule in:\n{sheet}"
    return match.group(1)


def window_color():
    return QApplication.palette().color(QPalette.ColorRole.Window)


def near(a: QColor, b: QColor, tolerance: int = 24) -> bool:
    return all(
        abs(x - y) <= tolerance
        for x, y in zip((a.red(), a.green(), a.blue()), (b.red(), b.green(), b.blue()))
    )


def pixels(widget, rect=None):
    """Every color in `rect` of a fresh grab of `widget` (all of it by default)."""
    image = widget.grab().toImage()
    rect = rect or image.rect()
    return [
        image.pixelColor(x, y)
        for y in range(rect.top(), rect.bottom() + 1)
        for x in range(rect.left(), rect.right() + 1)
    ]


class AllowActiveAndDisabled(QProxyStyle):
    """Lets the mouse make a disabled item the active one.

    Some platform styles allow it (it is what a disabled item "highlighted"
    under the mouse is); offscreen Fusion does not, and without this the
    disabled-item test would pass without testing anything.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_Menu_AllowActiveAndDisabled:
            return 1
        return super().styleHint(hint, option, widget, returnData)


def offscreen(widget):
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    return widget


@pytest.fixture
def window(qtbot):
    """A main window with a bar holding one menu: an enabled and a disabled item."""

    def build(**kwargs):
        win = offscreen(QMainWindow())
        qtbot.addWidget(win)
        win.setCentralWidget(QLabel("content"))
        bar = win.menuBar()
        menu = bar.addMenu("&Edit")
        enabled = menu.addAction("Enabled item")
        disabled = menu.addAction("Disabled item")
        disabled.setEnabled(False)
        apply_menus(bar, **kwargs)
        win.resize(480, 300)
        win.show()
        QApplication.processEvents()
        return win, bar, menu, enabled, disabled

    return build


@pytest.fixture
def dark_desktop(qapp):
    """The application palette with a dark Window, as the apps run under.

    Application-wide on purpose, and put back afterwards: that is where a
    desktop's palette lives. A palette set on the *window* instead does not
    reach a bar carrying a stylesheet — the stylesheet cuts the bar off from
    its parent's palette — and so would not be the situation being tested.
    """
    original = QPalette(QApplication.palette())
    dark = QPalette(original)
    dark.setColor(QPalette.ColorRole.Window, QColor(DARK_WINDOW))
    QApplication.setPalette(dark)
    yield QColor(DARK_WINDOW)
    QApplication.setPalette(original)


def open_menu(menu):
    offscreen(menu)
    menu.popup(QPoint(0, 0))
    QApplication.processEvents()
    return menu


def select(menu, action):
    menu.setActiveAction(action)
    QApplication.processEvents()
    assert menu.activeAction() is action
    return menu.actionGeometry(action)


# -- the gray edges ---------------------------------------------------------


def test_the_divider_border_is_the_divider_color():
    assert DIVIDER_BORDER == f"1px solid {DIVIDER_COLOR}"
    assert DIVIDER_COLOR == "#9a9a9a"


def test_the_bars_bottom_edge_is_gray_all_the_way_across(window):
    _win, bar, *_ = window()
    image = bar.grab().toImage()
    bottom = image.height() - 1
    row = [image.pixelColor(x, bottom) for x in range(image.width())]
    assert all(color == GRAY for color in row)


def gray_line_replaces_fusions_own(bar, surface):
    """Past the titles, every row above the bottom one is the bar's own
    surface, and the bottom row is the gray: one line, not two."""
    image = bar.grab().toImage()
    x = image.width() - 3
    column = [image.pixelColor(x, y) for y in range(image.height())]
    assert column[-1] == GRAY
    assert all(color == surface for color in column[:-1])


def test_the_gray_line_replaces_fusions_own(window):
    """Fusion draws a line of its own along the bar's bottom, a shade darker
    than the window. The border replaces it rather than sitting beside it."""
    _win, bar, *_ = window()
    gray_line_replaces_fusions_own(bar, window_color())


def test_on_a_dark_desktop_too(dark_desktop, window):
    """Where Fusion's line is the near-black one the gray exists to replace."""
    _win, bar, menu, *_ = window()
    gray_line_replaces_fusions_own(bar, dark_desktop)
    image = open_menu(menu).grab().toImage()
    assert image.pixelColor(0, image.height() // 2) == GRAY
    assert image.pixelColor(image.width() // 2, 3) == dark_desktop


def test_the_drop_down_has_a_gray_edge_on_all_four_sides(window):
    _win, _bar, menu, *_ = window()
    image = open_menu(menu).grab().toImage()
    w, h = image.width(), image.height()
    edges = (
        [image.pixelColor(x, 0) for x in range(w)]
        + [image.pixelColor(x, h - 1) for x in range(w)]
        + [image.pixelColor(0, y) for y in range(h)]
        + [image.pixelColor(w - 1, y) for y in range(h)]
    )
    assert all(color == GRAY for color in edges)


def test_the_drop_down_is_painted_in_the_window_color(window):
    _win, _bar, menu, *_ = window()
    image = open_menu(menu).grab().toImage()
    assert image.pixelColor(image.width() // 2, 3) == window_color()


def test_the_item_min_width_opens_up_the_menu(window):
    _win, _bar, menu, enabled, _disabled = window()
    open_menu(menu)
    assert menu.actionGeometry(enabled).width() >= 200


# -- selection colors -------------------------------------------------------


def test_by_default_a_selected_item_follows_the_palette(window):
    _win, _bar, menu, enabled, _disabled = window()
    rect = select(open_menu(menu), enabled)
    color = menu.grab().toImage().pixelColor(rect.left() + 3, rect.center().y())
    assert color == QApplication.palette().color(QPalette.ColorRole.Highlight)


def test_the_highlight_overrides_apply(window):
    _win, _bar, menu, enabled, _disabled = window(highlight="#ff0000", highlighted_text="#00ff00")
    rect = select(open_menu(menu), enabled)
    colors = pixels(menu, rect)
    assert menu.grab().toImage().pixelColor(rect.left() + 3, rect.center().y()) == RED
    assert any(near(color, GREEN, 60) for color in colors), "no text in the highlighted_text color"


def test_an_open_bar_title_takes_the_highlight(window):
    _win, bar, menu, *_ = window(highlight="#ff0000", hover="#0000ff")
    bar.setActiveAction(menu.menuAction())
    QApplication.processEvents()
    rect = bar.actionGeometry(menu.menuAction())
    assert bar.grab().toImage().pixelColor(rect.left() + 2, rect.center().y()) == RED


def test_a_hovered_bar_title_takes_the_hover(window):
    _win, bar, menu, *_ = window(highlight="#ff0000", hover="#0000ff")
    rect = bar.actionGeometry(menu.menuAction())
    center = QPointF(rect.center())
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        center,
        bar.mapToGlobal(center),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(bar, move)
    QApplication.processEvents()
    assert bar.activeAction() is menu.menuAction()
    assert bar.grab().toImage().pixelColor(rect.left() + 2, rect.center().y()) == BLUE


def test_no_hover_means_the_full_highlight():
    sheet = menu_style(highlight="#ff0000", highlighted_text="#00ff00")
    assert rule(sheet, "QMenuBar::item:selected") == rule(sheet, "QMenuBar::item:pressed")


def test_a_hover_is_a_background_only():
    """A wash over the title; its text keeps its own color."""
    assert "color" not in rule(menu_style(hover="#0000ff"), "QMenuBar::item:selected").replace(
        "background", ""
    )


def test_a_qcolor_keeps_its_alpha():
    sheet = menu_style(hover=QColor(158, 75, 46, 56))
    assert "rgba(158, 75, 46, 56)" in rule(sheet, "QMenuBar::item:selected")


def test_a_string_passes_through_verbatim():
    sheet = menu_style(hover="rgba(158, 75, 46, 56)")
    assert "rgba(158, 75, 46, 56)" in rule(sheet, "QMenuBar::item:selected")


# -- disabled items ---------------------------------------------------------


def test_a_disabled_item_under_the_mouse_is_not_highlighted(qtbot):
    menu = offscreen(QMenu())
    qtbot.addWidget(menu)
    style = AllowActiveAndDisabled("Fusion")
    style.setParent(menu)  # setStyle() does not take ownership
    menu.setStyle(style)
    menu.addAction("Enabled item")
    disabled = menu.addAction("Disabled item")
    disabled.setEnabled(False)
    apply_menus(menu, highlight="#ff0000", highlighted_text="#00ff00")
    rect = select(open_menu(menu), disabled)  # asserts it really is active

    image = menu.grab().toImage()
    assert image.pixelColor(rect.left() + 3, rect.center().y()) == window_color()
    colors = pixels(menu, rect)
    assert not any(near(color, RED, 60) for color in colors)
    assert not any(near(color, GREEN, 60) for color in colors)


# -- the font ---------------------------------------------------------------


def test_a_point_size_reaches_the_bar_and_the_menus():
    sheet = menu_style(point_size=17)
    assert "font-size: 17pt" in rule(sheet, "QMenuBar")
    assert "font-size: 17pt" in rule(sheet, "QMenu")


def test_no_point_size_leaves_the_font_alone():
    assert "font-size" not in menu_style()


# -- what is left alone -----------------------------------------------------


def test_only_the_widgets_passed_carry_the_sheet(window):
    win, bar, menu, *_ = window(point_size=12)
    assert bar.styleSheet() == menu_style(point_size=12)
    assert win.styleSheet() == ""
    assert menu.styleSheet() == ""  # it inherits from the bar instead


def test_every_widget_passed_is_styled(qtbot):
    one, two = QMenu(), QMenu()
    qtbot.addWidget(one)
    qtbot.addWidget(two)
    apply_menus(one, two, highlight="#ff0000")
    assert one.styleSheet() == two.styleSheet() == menu_style(highlight="#ff0000")


def test_nothing_application_wide_is_touched(qapp, window):
    palette = QApplication.palette()
    sheet = qapp.styleSheet()
    style = qapp.style()
    font = QApplication.font()
    window(highlight="#ff0000", point_size=20)
    assert QApplication.palette() == palette
    assert qapp.styleSheet() == sheet
    assert qapp.style() is style
    assert QApplication.font() == font


def test_nothing_keeps_a_menu_alive(qapp):
    gc.disable()
    try:
        menu = QMenu()
        menu.addAction(QAction("Item", menu))
        apply_menus(menu, highlight="#ff0000")
        alive = weakref.ref(menu)
        del menu
        assert alive() is None
    finally:
        gc.enable()
