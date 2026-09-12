"""The title bar: choosing the decoration, and repurposing the palette for it.

Everything here is Wayland-only. On any other platform the window manager
draws the title bar out of process, where neither the palette nor a decoration
plugin has anything to say about it, and `install()` returns without doing
anything.
"""

from __future__ import annotations

import os
import warnings

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QWidget

from .theme import DEFAULT_THEME, ChromeTheme, set_theme, theme

# The environment variable naming the Qt Wayland decoration plugin. Read inside
# the QApplication constructor and never again, which is why `configure()` has
# to run before that line rather than beside `install()`.
DECORATION_ENV = "QT_WAYLAND_DECORATION"

# What the window body should be painted with, captured by `install()` before
# it repurposes those roles for the decoration. Empty when the title bar was
# left alone, which is what makes `_apply_body_palette()` a no-op off Wayland.
_BODY_ROLES: dict[QPalette.ColorGroup, dict[QPalette.ColorRole, QColor]] = {}

# The font the window *body* should be drawn with, captured by `install()`
# before it puts the title's font on the application. `None` when the title bar
# was left alone, which is what makes `body_font()` fall through off Wayland.
_BODY_FONT: QFont | None = None

# The class the body font is registered against. Every widget inherits from
# `QWidget`, and `QApplicationPrivate::font(w)` resolves a class font by
# walking `w->inherits(key)` — so one entry covers the whole application.
_BODY_FONT_CLASS = "QWidget"

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

    The title's *font* is reached the same way and for the same reason — the
    decoration paints with the application font, so the application font is
    what has to carry the title's weight, and the body is handed its own font
    back. `_install_title_font()` has the details.

    Call this *after* any palette or font tuning the application does of its
    own: the body colors and the body font are captured at this moment, and a
    palette or font changed afterwards is one this never saw. An
    `app.setFont()` after this point is worse than merely unseen — it clears
    the class-font table `_install_title_font()` writes into, so the body font
    stops being handed back and the whole application inherits the title's
    weight.

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
    _install_title_font(app, chrome)
    # After the palette, so the filter's first widget already sees the roles
    # it has to hand back. See `_BodyPaletteFilter` for why every widget needs
    # visiting rather than just the windows.
    app.installEventFilter(_BODY_FILTER)


def _install_title_font(app: QApplication, chrome: ChromeTheme) -> None:
    """Put the title's font on the application, and the body's back on widgets.

    Same shape as the palette above, and for the same reason: the decoration
    has no font of its own to set. `QWaylandBradientDecoration::paint()` does
    `QFont font = p.font()` on a painter over the window's backing store —
    a non-widget paint device, so that font is `QGuiApplication::font()`, the
    plain application font. Making the title bold means making the
    *application* font bold, and then giving the body back the font it had.

    Two `setFont` calls, and **the order between them is not interchangeable**.
    `QApplication::setFont(font)` with no class name clears the class-font
    table on its way through, so the app-wide call has to come first or it
    wipes the entry the second one is about to rely on.

    Handing the body font back is a class font rather than the polish-time
    filter the palette needs, and that is the better tool here: a class font is
    the *default* a widget resolves against, so a widget that set its own font
    (the `sh` editor's fixed-width one, a view's larger point size) keeps it,
    and a stylesheet's `font-size` still merges on top. The filter would have
    to overwrite a widget's font to place it, and could not tell the two apart.
    It reaches everything for the reason `_BODY_FONT_CLASS` gives, so there is
    no per-widget leak to chase either — `QStyleSheetStyle` resolves a font
    from the *parent* widget, not from the application, which is exactly the
    thing it does not do for palettes.

    What it does not reach: the application font is now the title's, so any
    `QPainter` on a pixmap or image starts out bold, since that is the very
    path the decoration takes. Code drawing text on one wants `body_font()`.
    """
    global _BODY_FONT
    _BODY_FONT = QFont(app.font())

    title_font = QFont(_BODY_FONT)
    title_font.setWeight(chrome.title_font_weight)
    title_font.setStretch(chrome.title_font_stretch)

    app.setFont(title_font)  # app-wide: the font the decoration reads
    app.setFont(QFont(_BODY_FONT), _BODY_FONT_CLASS)  # ... and every widget back


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


def body_font() -> QFont:
    """The font the window *body* is drawn with.

    Not `QApplication.font()`: once `install()` has run that is the *title*
    font — bold, and possibly stretched — because the decoration paints with
    the application font and nothing else. Widgets are unaffected, since the
    body font is handed back to them as a class font, so this is only needed
    where the application font is read directly. In practice that means a
    `QPainter` over a pixmap or an image: its default font is
    `QGuiApplication::font()`, which is the same path the decoration takes, so
    text drawn on a pixmap — a glyph rendered into an icon, say — comes out
    bold unless it starts from here.

    Falls through to the application font when the title bar was left alone,
    which is the same font it would have read anyway.

    A copy, not the captured font itself: `QFont` is mutable and the obvious
    `f = body_font(); f.setPointSize(20)` would otherwise rewrite the font this
    module hands to every widget. Same hazard as `body_text_color()`, which
    records what it cost when it was left open.
    """
    return QFont(_BODY_FONT if _BODY_FONT is not None else QApplication.font())


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


# Marks the rule below as ours, so it is written once and never doubled up.
_POPUP_MARKER = "/* windowchrome */"


def _fix_popup_background(widget: QWidget) -> None:
    """Repaint a drop-down list that ignores its own palette.

    An **unstyled** `QComboBox` popup paints its background from
    `QApplication.palette()` at paint time, not from the palette of any widget
    in it — so the event filter cannot reach it, and the drop-down opens in the
    title bar's color. Measured: with every widget in the popup reading
    `Window = <body color>`, the popup still rendered the title bar's blue, and
    changing *only* the application palette (filter removed, no widget palette
    touched) moved it — proof that the paint follows the application palette.

    A stylesheet is what breaks the tie: any stylesheet on the combo or its
    view switches it to `QStyleSheetStyle`, which resolves from the widget
    palette instead. That is the whole reason this bug shows up in one app and
    not another — an app that pads its combo has already fixed it by accident.

    So the rule is written here, on the view, for popups that have no
    stylesheet of their own. A view the host has already styled is left alone:
    it is already resolving correctly, and overwriting the host's rule would
    be worse than the bug.

    Restricted to a view inside a popup window, which is what a drop-down is;
    an ordinary list or tree in a window paints from its own palette and needs
    nothing.
    """
    if not _BODY_ROLES or not isinstance(widget, QAbstractItemView):
        return
    window = widget.window()
    if window is widget or window.windowType() != Qt.WindowType.Popup:
        return

    sheet = widget.styleSheet()
    if sheet and _POPUP_MARKER not in sheet:
        return  # the host styled it; it already resolves from the palette
    rule = f"{_POPUP_MARKER} QAbstractItemView {{ background: {body_window_color().name()}; }}"
    if sheet != rule:
        widget.setStyleSheet(rule)


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
            _fix_popup_background(obj)
        return False


# Kept alive at module scope: installing a filter does not take ownership, and
# a collected filter is a dangling pointer in the application's event loop.
_BODY_FILTER = _BodyPaletteFilter()
