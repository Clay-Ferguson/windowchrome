"""The title bar: choosing the decoration, and repurposing the palette for it.

Everything here is Wayland-only. On any other platform the window manager
draws the title bar out of process, where neither the palette nor a decoration
plugin has anything to say about it, and `install()` returns without doing
anything. The border in `border.py` works everywhere.
"""

from __future__ import annotations

import os
import warnings

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

from .theme import DEFAULT_THEME, ChromeTheme, set_theme, theme

# The environment variable naming the Qt Wayland decoration plugin. Read inside
# the QApplication constructor and never again, which is why `configure()` has
# to run before that line rather than beside `install()`.
DECORATION_ENV = "QT_WAYLAND_DECORATION"

# What the window body should be painted with, captured by `install()` before
# it repurposes those roles for the decoration. Empty when the title bar was
# left alone, which is what makes `_apply_body_palette()` a no-op off Wayland.
_BODY_ROLES: dict[QPalette.ColorGroup, dict[QPalette.ColorRole, QColor]] = {}

# The three (group, role) pairs `QWaylandBradientDecoration::paint()` reads.
# Taken from the shipped plugin rather than from documentation: disassembling
# it shows exactly three calls to QPalette::brush, with these arguments.
_TITLEBAR_ROLES = (
    (QPalette.ColorGroup.Active, QPalette.ColorRole.Window),
    (QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText),
    (QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText),
)


def configure(chrome_theme: ChromeTheme = DEFAULT_THEME) -> None:
    """Set the theme and pick the decoration plugin. Call before QApplication.

    Two setup calls rather than one because the two halves happen at different
    moments: the decoration is chosen by an environment variable the Wayland
    platform plugin reads *during* the `QApplication` constructor, while the
    palette it paints from can only be touched once that object exists. This
    is the first half; `install()` is the second.

    `setdefault`, so an explicit `QT_WAYLAND_DECORATION` in the environment
    still wins — this is a default, not a policy.
    """
    set_theme(chrome_theme)
    os.environ.setdefault(DECORATION_ENV, chrome_theme.decoration)


def install(app: QApplication) -> None:
    """Color the window's title bar, by way of the application palette.

    On Wayland, GNOME implements no server-side decorations, so the title bar
    is drawn *by Qt, inside this process* — which is the only reason it can be
    colored at all. Which decorator runs is chosen by `QT_WAYLAND_DECORATION`,
    which `configure()` sets before the QApplication exists, because the
    platform plugin reads it during that constructor.

    Qt ships two decorators and defaults to `adwaita`, whose grays are
    compiled in: it links no QPalette symbol at all, so nothing here can move
    it. `bradient` paints from the application palette instead, and re-reads it
    on every repaint rather than caching it at construction.

    It reads `Window` and `WindowText` — the app's own surface and text roles,
    not roles of its own. So coloring the bar means repurposing them
    application-wide, and `_apply_body_palette()` is what hands them back to
    every widget as it is polished. A widget the filter somehow misses comes
    out wearing the title bar's colors, which is loud but not broken.

    Call this *after* any palette tuning the application does of its own: the
    body colors are captured at this moment, and a palette changed afterwards
    is a palette this never saw.

    A no-op off Wayland, where the platform draws the title bar and neither
    the palette nor the decorator has anything to say about it.
    """
    chrome = theme()
    chosen = os.environ.get(DECORATION_ENV)
    if chosen != chrome.decoration:
        # Warn and carry on. The failure mode of a botched integration is
        # otherwise a silently gray title bar and a session spent hunting for
        # why — the one bug this library invites.
        warnings.warn(
            f"{DECORATION_ENV} is {chosen!r}, not the theme's "
            f"{chrome.decoration!r}: the title bar will not take the theme's "
            f"colors. windowchrome.configure() must run before QApplication "
            f"is constructed, since the Wayland plugin reads that variable "
            f"during the constructor and never again.",
            RuntimeWarning,
            stacklevel=2,
        )

    if app.platformName() != "wayland":
        return

    palette = app.palette()
    for group, role in _TITLEBAR_ROLES:
        _BODY_ROLES.setdefault(group, {})[role] = palette.color(group, role)

    palette.setColor(
        QPalette.ColorGroup.Active, QPalette.ColorRole.Window, QColor(chrome.title_bg)
    )
    palette.setColor(
        QPalette.ColorGroup.Active,
        QPalette.ColorRole.WindowText,
        QColor(chrome.title_fg),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(chrome.title_fg_inactive),
    )
    app.setPalette(palette)
    # After the palette, so the filter's first widget already sees the roles
    # it has to hand back. See `_BodyPaletteFilter` for why every widget needs
    # visiting rather than just the windows.
    app.installEventFilter(_BODY_FILTER)


def body_window_color() -> QColor:
    """The surface color the window *body* is painted with.

    Not `QApplication.palette()`'s `Window`: on Wayland that role carries the
    title bar's color instead — see `install()`. Anything deriving a color for
    the body has to come here, or it is tinted with the title bar and, where
    it lightens or darkens what it read, wrong twice over. That is exactly
    what happened to the host app's splitter handle: it read the title bar
    blue and then lightened it, arriving at a brighter blue than the bar
    itself.

    Falls through to the application palette when the title bar was left
    alone, which is the same color it would have read anyway.

    A copy, not the captured color itself — see `body_text_color()`.
    """
    body = _BODY_ROLES.get(QPalette.ColorGroup.Active, {})
    return QColor(
        body.get(
            QPalette.ColorRole.Window,
            QApplication.palette().color(QPalette.ColorRole.Window),
        )
    )


def body_text_color() -> QColor:
    """The text color the window *body* is painted with.

    The counterpart to `body_window_color()`, and it exists for the same
    reason: `WindowText` is one of the three roles the title bar takes, so
    `QApplication.palette()` hands back the title bar's foreground once
    `install()` has run — white, typically — and anything deriving a body text
    color from it comes out invisible against the body's own surface. Reach for
    this instead wherever a muted or alpha-blended version of the window's text
    color is being computed.

    Falls through to the application palette when the title bar was left alone,
    which is the same color it would have read anyway.

    **A copy, not the captured color itself.** `QColor` is mutable and PyQt
    hands back the stored object, so a caller doing the obvious thing —
    `muted = body_text_color(); muted.setAlpha(180)` — would otherwise rewrite
    the body color this module hands to every widget, and the whole
    application's text would come out at 70% opacity. Measured: that is exactly
    what happened, visible as lightened antialiasing on every label in a
    dialog.
    """
    body = _BODY_ROLES.get(QPalette.ColorGroup.Active, {})
    return QColor(
        body.get(
            QPalette.ColorRole.WindowText,
            QApplication.palette().color(QPalette.ColorRole.WindowText),
        )
    )


def _apply_body_palette(widget: QWidget) -> None:
    """Give `widget` back the surface and text colors the title bar took.

    A no-op when the widget already has them — which is the common case, since
    a palette set on a widget propagates to its children — and a no-op when
    `install()` did not run, so this is safe to call on every widget in the
    application, which is what `_BodyPaletteFilter` does.
    """
    if not _BODY_ROLES:
        return

    palette = widget.palette()
    if all(
        palette.color(group, role) == color
        for group, roles in _BODY_ROLES.items()
        for role, color in roles.items()
    ):
        return

    for group, roles in _BODY_ROLES.items():
        for role, color in roles.items():
            palette.setColor(group, role, color)
    widget.setPalette(palette)


class _BodyPaletteFilter(QObject):
    """Restores the body colors on every widget, as it is polished.

    Palette inheritance alone is not enough, and the reason is worth knowing:
    **giving a widget a stylesheet severs it.** `QStyleSheetStyle` resolves a
    palette for a styled widget out of the *application* palette and assigns
    it, so the widget stops inheriting from its parent and starts wearing the
    title bar's colors — and everything below it inherits that in turn. An app
    that styles its menu bar, a splitter or its scroll bars — as the host of
    this library does — is not an edge case. A window is severed too, by being
    a window: a dialog, a popup menu or a `QMessageBox` resolves against the
    application palette however it is parented. Measured in that host: 22
    widgets leaked with the palette set on the main window alone, 0 with this.

    `QEvent.Polish` is where this is caught. Every widget gets exactly one,
    before it is first shown and after its constructor has set whatever
    stylesheet it is going to set, so one pass per widget fixes both causes
    with no bookkeeping. Filtering on the application means no call site has
    to remember: the failure mode of remembering is a widget that comes out in
    the title bar's color, which is how the menu bar was found.

    The type check is first and is an integer compare, which matters because
    an application-wide filter sees every event in the process.
    """

    #: `StyleChange` as well as `Polish`, because one polish per widget is not
    #: quite enough: a stylesheet set on an *ancestor* — a splitter, say, which
    #: is the parent of both its panes — repolishes the subtree below it,
    #: re-deriving those palettes from the application's after their own Polish
    #: has already been and gone. StyleChange is what that arrives as.
    #:
    #: And `PaletteChange`, because neither of those two is late enough on its
    #: own. **An application event filter runs before the receiver handles the
    #: event**, so on Polish the order is: this filter corrects the palette,
    #: and *then* `QWidget::event()` reaches `QStyleSheetStyle::polish()`,
    #: which re-derives one from the application palette and assigns it —
    #: overwriting the correction that was made moments earlier. Measured on a
    #: `QComboBox` popup inside a styled dialog: the view's `Window` role reads
    #: correctly at every Polish and StyleChange the filter sees, and is the
    #: title bar's color once everything settles, so the popup opened painted
    #: like the title bar. A combo popup is where this shows up because
    #: `QStyleSheetStyle` treats `QComboBox QAbstractItemView` as a styled
    #: sub-control and therefore always assigns it a palette, whether or not
    #: the app wrote a rule for one.
    #:
    #: `PaletteChange` is the event that assignment raises, which makes it the
    #: one trigger guaranteed to arrive *after* any palette is set, by anyone.
    #: It cannot loop: `_apply_body_palette()` returns without writing when the
    #: colors are already right, so this filter's own `setPalette` re-enters it
    #: exactly once and stops. That early return is load-bearing — remove it
    #: and this becomes infinite recursion.
    _TRIGGERS = frozenset(
        {QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.PaletteChange}
    )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt)
        if event.type() in self._TRIGGERS and isinstance(obj, QWidget):
            _apply_body_palette(obj)
        return False


# Kept alive at module scope: installing a filter does not take ownership, and
# a collected filter is a dangling pointer in the application's event loop.
_BODY_FILTER = _BodyPaletteFilter()
