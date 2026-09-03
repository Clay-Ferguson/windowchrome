"""The window around the view: its sizing, its buttons, and its registry.

Nothing here hands a dialog to `qtbot.addWidget`. These windows set
`WA_DeleteOnClose` and the autouse fixture closes them, so registering them
with pytest-qt as well means its teardown reaches for a widget that has
already deleted itself — which fails the *following* test, not this one.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QPushButton, QToolButton

from windowchrome import MarkdownDialog, close_markdown_windows, show_markdown
from windowchrome.markdowndialog import _WINDOWS, CONTENT_INSET, DEFAULT_WIDTH


@pytest.fixture
def a_md(docs):
    return docs / "a.md"


def visible_dialogs():
    return [w for w in _WINDOWS.values()]


# -- the window -------------------------------------------------------------


def test_it_shows_the_document(qtbot, a_md):
    dialog = show_markdown(a_md)
    assert "Alpha Guide" in dialog.view.document().toPlainText()


def test_the_title_falls_back_to_the_first_heading(qtbot, a_md):
    dialog = show_markdown(a_md)
    assert dialog.windowTitle() == "Alpha Guide"


def test_an_explicit_title_wins(qtbot, a_md):
    dialog = show_markdown(a_md, title="Sonar — User Guide")
    assert dialog.windowTitle() == "Sonar — User Guide"


def test_the_minimum_width_is_pinned_to_the_image_width(qtbot, a_md):
    """What keeps this to one render for the life of the window.

    Images are fitted once, to the content width. If the window could be
    dragged narrower than that, they would overflow and the only cure would
    be dropping the image cache and re-rendering — so the window cannot be.
    """
    dialog = show_markdown(a_md, width=760)
    assert dialog.minimumWidth() == 760
    assert dialog.view.horizontalScrollBar().maximum() == 0


def test_a_wide_image_fits_at_the_default_width(qtbot, a_md):
    dialog = show_markdown(a_md)
    assert dialog.width() == DEFAULT_WIDTH
    assert dialog.view.horizontalScrollBar().maximum() == 0
    assert CONTENT_INSET > 0


# -- buttons ----------------------------------------------------------------


def test_the_button_factory_is_used(qtbot, a_md):
    def factory(text):
        button = QToolButton()
        button.setText(text)
        button.setObjectName(f"made-{text}")
        return button

    dialog = show_markdown(a_md, button_factory=factory)
    # A QToolButton, so the type is proof the factory ran rather than the
    # default — and proof the factory may return any QAbstractButton.
    assert dialog.findChild(QToolButton, "made-Back") is not None
    assert dialog.findChild(QToolButton, "made-Close") is not None


def test_without_a_factory_the_buttons_are_plain(qtbot, a_md):
    dialog = show_markdown(a_md)
    assert len(dialog.findChildren(QPushButton)) == 2


def test_back_is_dim_until_there_is_somewhere_to_go(qtbot, a_md):
    dialog = show_markdown(a_md)
    back = dialog.findChildren(QPushButton)[0]
    assert not back.isEnabled()

    dialog.view.setSource(dialog.view.source())  # no-op, still nowhere to go
    assert not back.isEnabled()


# -- the registry -----------------------------------------------------------


def test_asking_twice_raises_the_same_window(qtbot, a_md):
    first = show_markdown(a_md)
    second = show_markdown(a_md)
    assert second is first
    assert len(_WINDOWS) == 1


def test_a_different_document_gets_its_own_window(qtbot, docs):
    first = show_markdown(docs / "a.md")
    second = show_markdown(docs / "b.md")
    assert first is not second
    assert len(_WINDOWS) == 2


def test_reopening_after_escape_gives_a_fresh_window(qtbot, a_md):
    """Escape is `reject()`, which deletes the widget without a closeEvent.

    A registry evicted in `closeEvent` would still be holding this dialog,
    and the next open would raise RuntimeError off the deleted wrapper.
    """
    first = show_markdown(a_md)
    first.reject()

    second = show_markdown(a_md)
    assert second is not first, "a dismissed window must not be handed back"
    assert "Alpha Guide" in second.view.document().toPlainText()
    assert len(_WINDOWS) == 1


def test_a_late_destroyed_does_not_evict_its_successor(qtbot, a_md):
    """`destroyed` arrives a turn after the close that caused it.

    Close A, open B for the same document, and A's notification lands with B
    already registered. Without the identity check in `_forget`, B is
    evicted and a third open stacks a duplicate window.
    """
    first = show_markdown(a_md)
    first.reject()
    second = show_markdown(a_md)

    qtbot.wait(50)  # let the first dialog's `destroyed` land

    assert len(_WINDOWS) == 1
    assert show_markdown(a_md) is second


def test_closing_removes_it_from_the_registry(qtbot, a_md):
    dialog = show_markdown(a_md)
    dialog.close()
    qtbot.wait(50)
    assert _WINDOWS == {}


def test_close_markdown_windows_closes_all_of_them(qtbot, docs):
    show_markdown(docs / "a.md")
    show_markdown(docs / "b.md")
    assert len(_WINDOWS) == 2

    close_markdown_windows()
    qtbot.wait(50)
    assert _WINDOWS == {}


def test_the_dialog_can_be_built_without_the_registry(qtbot, a_md):
    """`MarkdownDialog` is usable on its own — the registry is `show_markdown`'s."""
    dialog = MarkdownDialog(a_md)
    try:
        assert _WINDOWS == {}
        assert "Alpha Guide" in dialog.view.document().toPlainText()
    finally:
        dialog.close()


def test_the_title_follows_what_the_window_is_showing(qtbot, a_md):
    """A window that can be navigated cannot keep the title it opened with.

    The caller's title still wins for the document it was opened on — that is
    the one the host has a name for — and anything reached from there is named
    by its own first heading.
    """
    dialog = show_markdown(a_md, title="Sonar — Query Syntax")
    assert dialog.windowTitle() == "Sonar — Query Syntax"

    dialog.view.anchorClicked.emit(QUrl("b.md"))
    assert dialog.windowTitle() == "Beta"

    dialog.view.back()
    assert dialog.windowTitle() == "Sonar — Query Syntax"
