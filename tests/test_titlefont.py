"""The title bar's font: who gets it, who is handed the body's font back.

None of this can go through `install()`, which returns early off Wayland and
so does nothing at all under `QT_QPA_PLATFORM=offscreen`. `_install_title_font`
is called directly instead — it is the whole of the font half, and it takes the
application and the theme as arguments precisely so it can be.

What these tests are about is the *reach* of the two `setFont` calls: the
application font is what the Wayland decoration paints the title with, and
every widget has to be handed back the font it would have had. Nothing here is
about pixels Qt painted, and nothing here can see a title bar.
"""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QFont, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QWidget

from windowchrome import DEFAULT_THEME, ChromeTheme, body_font, titlebar

BOLD = ChromeTheme(title_font_weight=QFont.Weight.Bold.value)


@pytest.fixture
def installed(qapp):
    """Run the font half of `install()`, and undo it afterwards.

    The application font and the class-font table are process-wide state that
    `qapp` shares with every other test in the run, so restoring them is not
    tidiness: `setFont` with no class name is what clears the table, which
    makes putting the original font back the way to empty it again too.
    """
    original = QFont(qapp.font())

    def install(chrome_theme=BOLD):
        titlebar._install_title_font(qapp, chrome_theme)
        return qapp

    yield install

    titlebar._BODY_FONT = None
    qapp.setFont(original)


def painter_font(device=None):
    """The font a `QPainter` over a pixmap starts with.

    Which is the whole mechanism: `QWaylandBradientDecoration::paint()` reads
    exactly this and draws the title with it.
    """
    image = QImage(20, 20, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        return QFont(painter.font())
    finally:
        painter.end()


# -- the title font ---------------------------------------------------------


def test_the_application_font_carries_the_themes_weight(installed):
    app = installed(ChromeTheme(title_font_weight=900))
    assert app.font().weight() == 900


def test_the_application_font_carries_the_themes_stretch(installed):
    app = installed(ChromeTheme(title_font_stretch=115))
    assert app.font().stretch() == 115


def test_the_font_a_painter_on_a_pixmap_starts_with_is_the_title_font(installed):
    """The claim the whole approach rests on, so it is asserted directly."""
    assert painter_font().weight() == QFont.Weight.Normal.value
    installed()
    assert painter_font().weight() == QFont.Weight.Bold.value


def test_the_size_is_left_alone(installed):
    """Nothing here tries to set a point size, because the plugin discards it.

    `paint()` does `font.setPixelSize(14)` with the 14 compiled in, so a theme
    that moved the size would be a promise the title bar cannot keep.
    """
    app = installed()
    assert app.font().pointSize() == body_font().pointSize()


# -- and the body's font, handed back ---------------------------------------


def test_a_plain_widget_does_not_inherit_the_title_weight(installed, shown):
    installed()
    window = QWidget()
    label = QLabel("x", window)
    shown(window)
    assert window.font().weight() == QFont.Weight.Normal.value
    assert label.font().weight() == QFont.Weight.Normal.value


def test_a_top_level_widget_carries_the_title_font_until_it_is_shown(installed, shown):
    """The one gap in the class font's reach, pinned down rather than hidden.

    `QWidget`'s constructor seeds a *window's* font from `QApplication::font()`
    with no widget argument, which is the title font; the class font only
    reaches it when the font is re-resolved, at polish. So the bold font is
    there between the constructor and the first show — never painted with, but
    a window that measures `self.font()` in its own constructor measures the
    title font and sizes itself a little wide. `body_font()` is the answer
    there, the same as for a painter.

    A child is unaffected either way: its font resolves from a parent that has
    no explicitly-set attribute to pass down, so it falls back to the class
    font at once.
    """
    installed()
    window = QWidget()
    child = QLabel("x", window)
    assert window.font().weight() == QFont.Weight.Bold.value  # not yet shown
    assert child.font().weight() == QFont.Weight.Normal.value

    shown(window)
    assert window.font().weight() == QFont.Weight.Normal.value


def test_a_widget_in_a_styled_window_does_not_either(installed, qtbot):
    """A stylesheet severs palette inheritance; it does not sever the font.

    `QStyleSheetStyle` resolves a font from the *parent widget* and a palette
    from the *application*, which is why the palette needs a polish-time filter
    and the font does not. If that ever stopped being true, this is the test
    that would say so.
    """
    installed()
    window = QWidget()
    qtbot.addWidget(window)
    window.setStyleSheet("QWidget { background: #222; }")
    button = QPushButton("y", window)
    button.setStyleSheet("QPushButton { font-size: 15pt; }")
    window.show()
    qtbot.waitExposed(window)

    assert button.font().weight() == QFont.Weight.Normal.value
    assert button.font().pointSize() == 15  # the sheet's own rule still applies


def test_a_widget_that_set_its_own_font_keeps_it(installed, qtbot):
    """Why this is a class font and not a per-widget assignment.

    A class font is the default a widget resolves *against*, so the fixed-width
    font an editor sets in its constructor survives. A filter that assigned the
    body font to each widget would overwrite it, with no way to tell an
    explicit font from an inherited one.
    """
    editor = QTextEdit()
    qtbot.addWidget(editor)
    mono = QFont("monospace")
    mono.setPointSize(15)
    editor.setFont(mono)
    installed()

    assert editor.font().family() == "monospace"
    assert editor.font().pointSize() == 15


def test_the_app_wide_call_has_to_come_first(installed, qapp):
    """The ordering rule inside `_install_title_font`, as an assertion.

    `QApplication::setFont(font)` with no class name clears the class-font
    table on its way through. Done in the other order the body font is wiped
    the moment the title font is set, and every widget inherits the title's
    weight — so this is not a style preference about which line reads better.
    """
    body = QFont(qapp.font())
    title = QFont(body)
    title.setWeight(QFont.Weight.Bold)
    label = QLabel("x")

    qapp.setFont(body, "QWidget")  # the wrong way round, on purpose
    qapp.setFont(title)
    assert QApplication.font(label).weight() == QFont.Weight.Bold.value

    qapp.setFont(title)  # and the way `_install_title_font` does it
    qapp.setFont(body, "QWidget")
    assert qapp.font().weight() == QFont.Weight.Bold.value
    assert QApplication.font(label).weight() == QFont.Weight.Normal.value


# -- body_font() ------------------------------------------------------------


def test_body_font_is_the_font_from_before_the_install(installed, qapp):
    before = QFont(qapp.font())
    installed()
    assert body_font().weight() == before.weight()
    assert body_font().family() == before.family()


def test_body_font_falls_through_when_the_title_bar_was_left_alone(qapp):
    """Which is every platform but Wayland, where `install()` does nothing."""
    titlebar._BODY_FONT = None
    assert body_font().weight() == QApplication.font().weight()


def test_body_font_hands_back_a_copy(installed):
    """A caller resizing what it got must not resize the whole application."""
    installed()
    mine = body_font()
    mine.setPointSize(mine.pointSize() + 12)
    assert body_font().pointSize() != mine.pointSize()


# -- the theme's defaults ---------------------------------------------------


def test_the_inactive_title_color_matches_the_active_one():
    """So the title does not dim the moment the window is dragged.

    An interactive move takes keyboard focus, and `bradient` then paints the
    title from the palette's `Disabled` group. Defaulting the two to the same
    color is the whole of the fix, so the default is worth pinning down.
    """
    assert DEFAULT_THEME.title_fg_inactive == DEFAULT_THEME.title_fg


def test_the_title_is_bold_by_default():
    assert DEFAULT_THEME.title_font_weight == QFont.Weight.Bold.value
    assert DEFAULT_THEME.title_font_stretch == 100  # no stretch unless asked for
