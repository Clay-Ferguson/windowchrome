"""Loading, links, fragments and images.

Nothing here asserts on colors or formats, because the view sets none: it
renders what Qt renders and never modifies the document. What it adds is
navigation and image fitting, which is what these test.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QTextDocument

from windowchrome import MarkdownView, heading_slug, heading_slugs


@pytest.fixture
def view(docs, shown):
    v = shown(MarkdownView())
    v.set_image_width(700)
    v.load(docs / "a.md")
    return v


def slugs(view):
    return heading_slugs([b.text() for b in view.heading_blocks()])


def untouched(view):
    """True if nothing has modified the document since it was rendered.

    `isModified()` is Qt's own answer to that, and it is the guard that keeps
    a styling pass from creeping back in: every one of them would have to
    change the document, which is what broke its layout before.
    """
    return not view.document().isModified()


# -- slugs ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Query syntax", "query-syntax"),
        ("  Padded  ", "padded"),
        ("Sonar — User Guide", "sonar--user-guide"),
        ("search.included", "searchincluded"),
        ("Read/write & more!", "readwrite--more"),
        ("...", ""),
    ],
)
def test_heading_slug(text, expected):
    assert heading_slug(text) == expected


def test_repeated_headings_are_numbered_like_github():
    assert heading_slugs(["Repeat", "Other", "Repeat", "Repeat"]) == [
        "repeat",
        "other",
        "repeat-1",
        "repeat-2",
    ]


# -- anchors ----------------------------------------------------------------


def test_every_heading_is_reachable(view):
    found = slugs(view)
    assert "alpha-guide" in found
    assert "second" in found
    # The document repeats "Repeat", which is what makes the numbering real
    # rather than theoretical.
    assert "repeat" in found
    assert "repeat-1" in found


def test_the_document_is_never_modified(view):
    """The constraint the whole design rests on."""
    assert untouched(view)
    view.scroll_to_heading("pictures")
    view.anchorClicked.emit(QUrl("#second"))
    assert untouched(view)


def test_in_page_link_scrolls(view):
    view.anchorClicked.emit(QUrl("#pictures"))
    assert view.verticalScrollBar().value() > 0


def test_fragments_still_work_after_going_back(view):
    """`backward()` re-renders the document from scratch.

    Nothing has to be re-applied to it for a fragment link to keep working,
    which is the point: the headings are read at the moment they are needed.
    """
    view.anchorClicked.emit(QUrl("b.md"))
    view.back()
    assert "pictures" in slugs(view)
    view.anchorClicked.emit(QUrl("#pictures"))
    assert view.verticalScrollBar().value() > 0
    assert untouched(view)


def test_an_unknown_fragment_is_reported_rather_than_guessed(view):
    assert view.scroll_to_heading("pictures")
    assert not view.scroll_to_heading("no-such-heading")


# -- navigation -------------------------------------------------------------


def test_relative_link_navigates_in_place(view):
    view.anchorClicked.emit(QUrl("b.md"))
    assert "Beta Heading" in view.document().toPlainText()
    assert view.can_go_back()


def test_back_returns_to_the_scroll_position_it_left(view):
    view.anchorClicked.emit(QUrl("#pictures"))
    left_at = view.verticalScrollBar().value()
    assert left_at > 0

    view.anchorClicked.emit(QUrl("b.md"))
    view.back()

    assert "Alpha Guide" in view.document().toPlainText()
    assert view.verticalScrollBar().value() == left_at


def test_link_with_both_a_path_and_a_fragment_loads_and_scrolls(view, shown):
    # `b.md` is short, so give the view a window it cannot fit it in.
    view.resize(300, 120)
    view.anchorClicked.emit(QUrl("b.md#beta-heading"))
    assert "Beta Heading" in view.document().toPlainText()


def test_a_link_to_nothing_changes_nothing(view):
    """A missing target must not reach `setSource`.

    It does not fail there: it renders an empty document and pushes a
    history entry for it, which is a worse outcome than the click doing
    nothing at all.
    """
    before = view.document().characterCount()
    view.anchorClicked.emit(QUrl("gone.md"))
    assert view.document().characterCount() == before
    assert not view.can_go_back()


def test_an_external_link_leaves_the_document_alone(view):
    class Handler(QObject):
        def __init__(self):
            super().__init__()
            self.seen = []

        @pyqtSlot(QUrl)
        def handle(self, url):
            self.seen.append(url.toString())

    handler = Handler()
    QDesktopServices.setUrlHandler("https", handler, "handle")
    try:
        before = view.document().characterCount()
        view.anchorClicked.emit(QUrl("https://example.com/x"))
        assert handler.seen == ["https://example.com/x"]
        assert view.document().characterCount() == before
    finally:
        QDesktopServices.unsetUrlHandler("https")


# -- rendering --------------------------------------------------------------


def test_tables_and_code_survive(view):
    assert "x = 1" in view.document().toPlainText()


def test_a_wide_image_is_fitted_on_the_first_render(view):
    assert view.horizontalScrollBar().maximum() == 0


def test_a_small_image_is_not_upscaled(view, docs):
    resource = view.document().resource(
        QTextDocument.ResourceType.ImageResource,
        QUrl.fromLocalFile(str(docs / "small.png")),
    )
    assert resource is not None
    assert resource.size().width() == 40


def test_a_wide_image_is_scaled_to_the_width_it_was_given(view, docs):
    resource = view.document().resource(
        QTextDocument.ResourceType.ImageResource,
        QUrl.fromLocalFile(str(docs / "wide.png")),
    )
    assert resource.size().width() == 700
    # Proportional: 1200x900 scaled to 700 wide is 525 tall, not squashed.
    assert resource.size().height() == 525


def test_a_broken_image_does_not_raise(docs, shown):
    (docs / "broken.png").write_bytes(b"not an image")
    (docs / "broken.md").write_text("# Broken\n\n![x](broken.png)\n")
    view = shown(MarkdownView())
    view.load(docs / "broken.md")
    assert "Broken" in view.document().toPlainText()


# -- loading ----------------------------------------------------------------


def test_a_missing_file_says_so_rather_than_raising(docs, shown):
    view = shown(MarkdownView())
    view.load(docs / "nowhere.md")
    assert "Not available" in view.document().toPlainText()


def test_set_markdown_resolves_links_against_its_base_dir(docs, shown):
    view = shown(MarkdownView())
    view.set_markdown("# Inline\n\n[go](b.md)\n", docs)
    view.anchorClicked.emit(QUrl("b.md"))
    assert "Beta Heading" in view.document().toPlainText()


def test_document_title_is_the_first_heading(view):
    assert view.document_title() == "Alpha Guide"
