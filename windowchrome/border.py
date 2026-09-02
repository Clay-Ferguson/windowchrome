"""The border painted inside the window, and the menu-bar rule that insets it.

This half is not Wayland-specific: it is ordinary layout and an ordinary
stylesheet, so it paints the same everywhere. It exists because the
decoration's own border cannot be widened — `QWaylandBradientDecoration::margins()`
returns a compiled-in `QMargins{3, 30, 3, 3}` with no font, palette or
environment input — so the only way to a thicker frame is to paint one just
inside the window, flush against the decoration's 3px and in the same color,
so the two read as one.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from .theme import theme
from .titlebar import body_window_color

# The object names the stylesheet's two rules key on. Exposed because a host
# writing rules of its own has to know what not to collide with.
FRAME_OBJECT_NAME = "windowFrame"
BODY_OBJECT_NAME = "windowBody"


def window_border_style() -> str:
    """Qt stylesheet painting the theme's border width inside the window.

    Three rules, and each one covers a different part of the same frame: the
    `QMainWindow` itself is what shows through the margin `menu_bar_style()`
    puts around the menu bar, `#windowFrame` is the strip down the sides and
    along the bottom, and `#windowBody` puts the ordinary surface color back
    under the content so the border color is a border rather than a backdrop.

    Object-name selectors rather than `QWidget`, which would match every
    widget in the window: a stylesheet set on a window is consulted for all of
    its descendants, so an unqualified rule here would paint the whole app.

    `QWidget#windowFrame` matches a `QDialog` too — Qt type selectors match
    subclasses, unlike CSS — which is why one rule covers the main window and
    every dialog.
    """
    chrome = theme()
    return f"""
        QMainWindow {{ background: {chrome.title_bg}; }}
        QWidget#{FRAME_OBJECT_NAME} {{ background: {chrome.title_bg}; }}
        QWidget#{BODY_OBJECT_NAME} {{ background: {body_window_color().name()}; }}
    """


def menu_bar_style() -> str:
    """The `QMenuBar` rule that insets the bar inside the border.

    Concatenate it into whatever menu stylesheet the host already has; it
    styles nothing but the bar's own margins and background.

    Only the horizontal margin: measured, `QMenuBar` ignores `margin-top` and
    `margin-bottom` outright, and applies the left/right value to its *height*
    as well — a 20px horizontal margin takes a 23px bar to 63px. That quirk is
    doing useful work here, so it is left alone rather than fought: it is what
    puts the border above and below the bar too, giving one even inset on all
    four sides. Setting the two vertical properties as well looks tidier and
    changes nothing.

    The background is restated rather than left to the palette because the
    margin exposes what is behind the bar: a bar that inherited a transparent
    background would let the border color through the bar itself as well. Note
    also that `QMainWindow` lays the bar out itself, so the margin never moves
    its geometry, only what it paints inside it — the color showing through is
    the *window's* background, which is what `window_border_style()`'s
    `QMainWindow` rule is for.
    """
    return f"""
        QMenuBar {{
            margin-left: {theme().border_width}px;
            margin-right: {theme().border_width}px;
            background: {body_window_color().name()};
        }}
    """


def bordered_body(frame: QWidget, top: int | None = None) -> QWidget:
    """Give `frame` the window border, and return the widget to build inside.

    Two widgets are needed rather than one, because a border is a color the
    content must not sit on: `frame` is painted in the border color and insets
    what it holds, and the widget handed back is painted in the ordinary
    surface color. **Build into the return value, not into `frame`.**

    `top` exists for a main window whose menu bar sits above this and carries
    its own inset (see `menu_bar_style()`); giving both one would draw a
    colored line *between* the menu bar and the content rather than a border
    around them. Pass `top=0` there. A dialog has nothing above it and takes
    the default, which is the theme's border width.

    The stylesheet goes on `frame.window()`, which is the frame itself for a
    dialog and the `QMainWindow` for the central widget — the main window
    needs the rule on itself regardless, since the menu bar's margin exposes
    the window's own background rather than the frame's.

    A stylesheet the window already carries is **kept**, with the border rules
    put in front of it rather than over the top of it: an application whose
    window styles itself — one that paints its own background to report state,
    say — would otherwise lose that styling to this call, silently and at
    construction time. In front, so the host's rules come last and win any tie
    of equal specificity. The corollary is an ordering rule: call this *after*
    the window has set its own stylesheet, since a later `setStyleSheet()`
    replaces rather than appends and would take the border with it.

    At a border width of 0 this is the layout it replaced, with one extra
    widget in it.
    """
    width = theme().border_width
    if top is None:
        top = width

    frame.setObjectName(FRAME_OBJECT_NAME)
    window = frame.window()
    window.setStyleSheet(window_border_style() + window.styleSheet())

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(width, top, width, width)
    layout.setSpacing(0)

    body = QWidget()
    body.setObjectName(BODY_OBJECT_NAME)
    layout.addWidget(body)
    return body
