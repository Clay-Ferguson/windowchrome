"""A window around a `MarkdownView`: `MarkdownDialog` and `show_markdown`.

Modeless, because help is read *beside* the thing it is about rather than on
top of it, and because a second request for a document people already have
open should raise that window rather than stack another copy of it.

The dialog owns no look of its own beyond its layout. Buttons come from the
host application through `button_factory`, since the four applications using
this library each build a button differently and none of their conventions
belongs here.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .markdownview import MarkdownView

# Wide enough for a document with tables in it; the old hand-built help
# dialogs these replace were around 520 and wrapped every table row.
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 700

# What the frame, the layout margins and a (possibly widened) scroll bar take
# out of the window's width before the text starts. Images are fitted to what
# is left. Generous rather than exact: fitting an image a little narrower than
# it could be costs nothing, and one pixel too wide costs a scroll bar.
CONTENT_INSET = 60

ButtonFactory = Callable[[str], QAbstractButton]


class MarkdownDialog(QDialog):
    """One markdown document in a modeless window, with Back and Close.

    `view` and `button_row` are public: an application that needs to style
    what the button factory cannot reach — a scroll bar, an extra button —
    reaches them through the dialog `show_markdown()` hands back.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        button_factory: ButtonFactory | None = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        super().__init__(parent)
        # A real window rather than a bare dialog frame, so the decoration
        # draws minimise and maximise. A long document wants maximise.
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(width, height)
        # Pinned to the width images were fitted to, which is what keeps this
        # to a single render for the life of the window: the images can never
        # be too wide for the view, so nothing ever has to be re-scaled.
        # Widening is free — an image stays its size rather than upscaling.
        self.setMinimumWidth(width)

        self.view = MarkdownView(self)
        self.view.set_image_width(max(width - CONTENT_INSET, 1))

        # A bare QPushButton when the host supplies nothing, deliberately: it
        # comes out wearing the desktop theme, which is visible, rather than
        # silently almost matching.
        make: ButtonFactory = button_factory or QPushButton
        self._back = make("Back")
        self._close = make("Close")
        self._back.setEnabled(False)
        self._back.clicked.connect(self.view.back)
        self._close.clicked.connect(self.reject)
        self.view.backwardAvailable.connect(self._back.setEnabled)

        self.button_row = QHBoxLayout()
        self.button_row.addWidget(self._back)
        self.button_row.addStretch(1)
        self.button_row.addWidget(self._close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addLayout(self.button_row)

        self._title = title
        self._home = str(Path(path).resolve())
        # Connected after the view's own handler, which is what decorates the
        # document — so `document_title()` is answerable by the time this runs.
        self.view.sourceChanged.connect(self._retitle)
        self.view.load(path)
        self._retitle(self.view.source())

    def _retitle(self, url: QUrl) -> None:
        """Name the window after whatever it is currently showing.

        A window that can be navigated cannot keep the title it opened with:
        following a link out of the Query Syntax page left a window headed
        "Query Syntax" showing the User Guide. The caller's title still wins
        for the document the window was opened on, since that is the one the
        host has a name for; anything reached from there is named by its own
        first heading.
        """
        at_home = url.isEmpty() or url.toLocalFile() == self._home
        if at_home and self._title:
            self.setWindowTitle(self._title)
            return
        self.setWindowTitle(self.view.document_title() or Path(self._home).name)


# Open windows by the resolved path of what they are showing. Module state
# rather than something the host holds, because "is this document already
# open?" is a question about the desktop, not about any one caller.
_WINDOWS: dict[str, MarkdownDialog] = {}


def _forget(key: str, dialog: MarkdownDialog) -> None:
    # Identity, and never a method call on `dialog` — this also runs from
    # `destroyed`, by which point the C++ object is gone and touching it
    # raises. The check matters because a dialog is forgotten twice, and the
    # second notification arrives a turn late: close A, open B for the same
    # path, and A's `destroyed` lands with B already registered. Without the
    # check B is evicted, and a third open stacks a duplicate window.
    if _WINDOWS.get(key) is dialog:
        del _WINDOWS[key]


def show_markdown(
    path: str | os.PathLike[str],
    parent: QWidget | None = None,
    *,
    title: str | None = None,
    button_factory: ButtonFactory | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> MarkdownDialog:
    """Show `path` in a modeless window, or raise the one already showing it."""
    key = str(Path(path).resolve())
    existing = _WINDOWS.get(key)
    if existing is not None:
        try:
            existing.showNormal()
            existing.raise_()
            existing.activateWindow()
            return existing
        except RuntimeError:
            # Closed with Escape a moment ago: `reject()` deletes the widget
            # without ever calling `closeEvent`, and `destroyed` has not been
            # delivered yet. Drop it and open a fresh one.
            _WINDOWS.pop(key, None)

    dialog = MarkdownDialog(
        path,
        parent,
        title=title,
        button_factory=button_factory,
        width=width,
        height=height,
    )
    _WINDOWS[key] = dialog
    # `finished` first, and it is the one that matters: it is emitted
    # synchronously by close(), reject() and Escape, whereas deletion is a
    # `deleteLater` that lands on a later turn. Evicting only on `destroyed`
    # leaves a window that has been dismissed still registered, so the next
    # open "raises" a dialog on its way to being deleted and hands back a
    # window that vanishes a moment later. `destroyed` stays as the backstop
    # for a dialog that is torn down without ever being closed — with its
    # parent, say.
    dialog.finished.connect(lambda *_: _forget(key, dialog))
    dialog.destroyed.connect(lambda *_: _forget(key, dialog))
    dialog.show()
    return dialog


def close_markdown_windows() -> None:
    """Close every window this module opened.

    Worth calling from a main window's `closeEvent`. A parented dialog does
    not keep the application alive — it has a transient parent, so it is not
    the "last window" as far as `quitOnLastWindowClosed` is concerned — but it
    does stay on screen for as long as it takes the application to notice,
    and a help window outliving the window it is about is wrong on its face.
    """
    # A copy: closing each one mutates the dict it would otherwise be walking.
    for dialog in list(_WINDOWS.values()):
        dialog.close()
