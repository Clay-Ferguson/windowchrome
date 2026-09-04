"""A markdown document in a widget: `MarkdownView`.

Qt renders markdown itself — `QTextBrowser.setMarkdown()` and
`setSource(url, MarkdownResource)` handle headings, tables, fenced code,
blockquotes, task lists, links and images — so nothing here parses markdown,
styles it, or modifies it. No markdown package is a dependency.

**This view never modifies the document it is showing.** That is a deliberate
constraint rather than an accident of what was needed. An earlier version
patched the rendered document after the fact — merging an anchor onto every
heading, a color onto every link, a background onto every code block — and
several hundred such changes to a document Qt is laying out incrementally
stops the layout part way through: everything past that point keeps a height
of zero, and a whole run of paragraphs renders as a band of blank space with
the text present but invisible. Qt has a way to batch changes safely, but the
better answer was to stop making them. What is left is two things Qt asks a
subclass to provide anyway:

- `loadResource()` — where Qt asks for an image and we hand back one already
  scaled to fit. It is the documented extension point for exactly this.
- link handling — `setOpenLinks(False)` plus an `anchorClicked` handler, so a
  `#fragment` scrolls, a relative `.md` opens in place, and nothing reaches
  `setSource()` that is not an existing local file.

Everything else is a read: headings are *found* to resolve a fragment link,
not marked up to make one work.

Kept separate from `markdowndialog` deliberately: markdown is not always shown
in a dialog, and a view that could only exist inside one would have to be
reimplemented the first time it is wanted anywhere else.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QImage, QTextDocument
from PyQt6.QtWidgets import QTextBrowser, QWidget

# What a relative link may open *in the view*. Anything else that exists on
# disk is handed to the desktop, which is what knows about PDFs and images.
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown", ".txt"})

# Everything but word characters, spaces and hyphens comes out of a slug.
_SLUG_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)

# White space between the text and the edge of the view, on all four sides.
# Qt's default is 4px, which puts the first character hard against the frame
# and the longest line hard against the scroll bar — a document rendered with
# no margin at all reads as broken rather than as plain.
#
# This is a property of the *document*, not a change *to* it: it is the root
# frame's margin, set once before anything is loaded, so it costs no format
# merges and does not trip the layout failure described in the module
# docstring. Measured: it survives `setSource`, a `backward()` and
# `set_markdown()` without being re-applied, and leaves `isModified()` false.
DOCUMENT_MARGIN = 20


def heading_slug(text: str) -> str:
    """GitHub's anchor slug for one heading, from its *rendered* text.

    Rendered, not source, and that is the whole subtlety: the markdown
    importer has already eaten the backticks and the emphasis by the time a
    heading is a text block, so "## `search.included`" arrives here as
    "search.included" and comes out "searchincluded" — which is exactly what
    GitHub produces for the same heading, so a link written against the file
    on GitHub resolves against the file in this widget.
    """
    return _SLUG_STRIP.sub("", text.strip().lower()).replace(" ", "-")


def heading_slugs(texts: list[str]) -> list[str]:
    """`heading_slug` over a document's headings, with repeats disambiguated.

    A repeated heading gets `-1`, `-2`, … after the first, the way GitHub
    numbers them. This is a separate function rather than a loop inside the
    lookup because anything that wants to *check* a document's links has to
    number them identically — a checker with its own copy of this rule is a
    checker that will eventually disagree with the view.
    """
    seen: dict[str, int] = {}
    slugs = []
    for text in texts:
        slug = heading_slug(text)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        slugs.append(f"{slug}-{count}" if count else slug)
    return slugs


class MarkdownView(QTextBrowser):
    """A read-only markdown document, with working links and fitted images.

    `image_width` is the width images are fitted to, and defaults to the
    viewport's own width when the view is used on its own rather than in a
    `MarkdownDialog`.
    """

    def __init__(self, parent: QWidget | None = None, *, image_width: int = 0) -> None:
        super().__init__(parent)
        self._image_width = image_width
        self._base_url = QUrl()
        self.document().setDocumentMargin(DOCUMENT_MARGIN)

        # Qt's own link handling is what has to be off. `setSource` on an http
        # URL or a path that does not exist does not fail: it renders an empty
        # document and pushes a history entry for it, and `openExternalLinks`
        # does not guard it, because that flag is only consulted on the click
        # path. So every click comes here instead and nothing reaches
        # `setSource` that has not been stat'd first.
        self.setOpenLinks(False)
        self.setReadOnly(True)
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.sourceChanged.connect(self._on_source_changed)

    # -- content ------------------------------------------------------------

    def set_image_width(self, width: int) -> None:
        """Fit images to `width` pixels rather than to the viewport.

        Set before loading. A container knows its content width before it has
        been laid out, and the point of fitting images is that they are the
        right size on the first render rather than after one.
        """
        self._image_width = width

    def load(self, path: str | os.PathLike[str]) -> None:
        """Render the markdown file at `path`. Never raises.

        An unreadable file renders a message saying so, the way a preview pane
        reports a file it cannot show rather than failing.
        """
        target = Path(path)
        try:
            readable = target.is_file() and os.access(target, os.R_OK)
        except OSError:
            readable = False
        if not readable:
            self.set_markdown(
                f"# Not available\n\n`{target}` could not be read.", target.parent
            )
            return
        self.setSource(
            QUrl.fromLocalFile(str(target.resolve())),
            QTextDocument.ResourceType.MarkdownResource,
        )

    def set_markdown(
        self, text: str, base_dir: str | os.PathLike[str] | None = None
    ) -> None:
        """Render `text`, resolving its relative links and images under `base_dir`."""
        self.clearHistory()
        if base_dir is not None:
            base = QUrl.fromLocalFile(str(Path(base_dir).resolve()) + os.sep)
            self._base_url = base
            self.document().setBaseUrl(base)
        else:
            self._base_url = QUrl()
        self.setMarkdown(text)

    def document_title(self) -> str:
        """The first H1, or "" — `historyTitle()` is empty for markdown."""
        block = self.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() == 1:
                return block.text().strip()
            block = block.next()
        return ""

    # -- history ------------------------------------------------------------

    def back(self) -> None:
        """The previous document, at the scroll position it was left at.

        Qt's own history does the whole of this, scroll position included, so
        there is no stack and no bookkeeping here to get wrong.
        """
        self.backward()

    def can_go_back(self) -> bool:
        return self.isBackwardAvailable()

    # -- fragments ----------------------------------------------------------

    def heading_blocks(self) -> list:
        """Every heading in the document, in order. A read, not a change."""
        blocks = []
        block = self.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel():
                blocks.append(block)
            block = block.next()
        return blocks

    def scroll_to_heading(self, slug: str) -> bool:
        """Scroll to the heading `slug` names. True if there was one.

        This is what replaces `scrollToAnchor()`, and why the document is
        never modified: Qt's markdown importer gives headings no anchor names,
        so the obvious fix is to inject them — which means changing the
        document, which is what broke its layout. Finding the heading and
        asking where it sits costs nothing and changes nothing.

        Asking for a block's rectangle lays the document out as far as that
        block, so this is safe to call from `sourceChanged`, before Qt has
        finished laying out the rest.
        """
        blocks = self.heading_blocks()
        for block, name in zip(blocks, heading_slugs([b.text() for b in blocks])):
            if name != slug:
                continue
            top = self.document().documentLayout().blockBoundingRect(block).y()
            self.verticalScrollBar().setValue(int(top))
            return True
        return False

    # -- images -------------------------------------------------------------

    def loadResource(self, rtype: int, name: QUrl):  # noqa: N802 - Qt's name
        """Hand the layout an image that already fits.

        Qt does not read image files itself: it asks for them here, during
        layout and before the first paint, and lays out whatever comes back at
        the size it comes back. So returning an already-scaled image is the
        whole of fitting one — no walking the document afterwards rewriting
        `QTextImageFormat` widths, no second layout pass, and no flash of an
        oversized image.

        Note the base implementation returns the file's raw bytes as a
        QByteArray rather than an image; decoding them here is not optional.
        """
        data = super().loadResource(rtype, name)
        if rtype != QTextDocument.ResourceType.ImageResource.value:
            return data

        image = QImage()
        if isinstance(data, QByteArray):
            image.loadFromData(data)
        elif isinstance(data, QImage):
            image = data
        elif data is not None and hasattr(data, "toImage"):
            image = data.toImage()

        # The margin is inside the viewport, so the room an image actually
        # has is the viewport less both sides of it.
        fallback = self.viewport().width() - 2 * int(self.document().documentMargin())
        width = self._image_width or max(fallback - 1, 1)
        # Down only. A small inline icon is already the size it wants to be,
        # and upscaling one would only make it blurry.
        if image.isNull() or image.width() <= width:
            return data
        return image.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)

    # -- links --------------------------------------------------------------

    def _base(self) -> QUrl:
        if not self._base_url.isEmpty():
            return self._base_url
        return self.document().baseUrl()

    def _on_source_changed(self, url: QUrl) -> None:
        self._base_url = url
        if url.fragment():
            self.scroll_to_heading(url.fragment())
        # Qt restores the history's scroll position after this returns, which
        # is the order we want: coming *back* to a page lands where it was
        # left, rather than at whichever fragment first brought us to it.

    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() and url.scheme() != "file":
            QDesktopServices.openUrl(url)
            return

        if not url.path():
            self.scroll_to_heading(url.fragment())
            return

        target = self._base().resolved(url)
        local = Path(target.toLocalFile())
        try:
            exists = local.is_file()
        except OSError:
            exists = False
        if not exists:
            # Silence is the right answer: handing this to `setSource` would
            # blank the document, and handing it to the desktop would open
            # nothing at best.
            return
        if local.suffix.lower() in MARKDOWN_SUFFIXES:
            self.setSource(target, QTextDocument.ResourceType.MarkdownResource)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(local)))
