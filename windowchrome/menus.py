"""A menu bar and drop-down menus with visible edges and room around each item.

Like the scroll bars and the radio buttons: no setup, no platform
requirement, and nothing to call before or after the QApplication. A host
styles one menu bar (or one standalone menu) at a time.

Left to Fusion on a dark palette, the line under the menu bar and the edge
round a drop-down come out near-black, and vanish against the dark desktop;
and the items are packed at the bare height of their text. Both are fixed
here by drawing the bar and its menus from a stylesheet, in which only the
selection colors and the font size are the host's to choose.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor

# The light gray of every line the apps draw across or round a window's
# contents — under the menu bar, round a drop-down, above a status bar — in
# place of Fusion's near-black. Pinned rather than derived from the palette,
# because it has to read against a light surface and a dark one alike.
DIVIDER_COLOR = "#9a9a9a"
DIVIDER_BORDER = f"1px solid {DIVIDER_COLOR}"

# Room around the bar, a title on it, a drop-down, and an item in one. The
# desktop's own sizes suit a mouse that never misses.
MENU_BAR_PADDING = "2px 4px"
MENU_BAR_ITEM_PADDING = "6px 14px"
MENU_PADDING = "6px 0"
MENU_ITEM_PADDING = "8px 22px"

# The narrowest an item in a drop-down is drawn, in pixels. It is what opens
# a gap between a label and its right-aligned shortcut, which otherwise sit
# almost touching ("Undo Cut Ctrl+Z").
MENU_ITEM_MIN_WIDTH = 200


def _css_color(color: QColor | str) -> str:
    """A color as a stylesheet value.

    A string passes through verbatim, so `palette(...)` and `rgba(...)` work
    as written. A QColor is written as `rgba(...)`, never `.name()`, which
    drops the alpha a hover wash depends on.
    """
    if isinstance(color, QColor):
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
    return color


def menu_style(
    *,
    highlight: QColor | str | None = None,
    highlighted_text: QColor | str | None = None,
    hover: QColor | str | None = None,
    point_size: int | None = None,
) -> str:
    """Qt stylesheet for a menu bar and its drop-downs.

    The bar's bottom edge and the drop-down's border are `DIVIDER_BORDER`.
    On the bar the border *replaces* Fusion's dark line rather than being
    drawn over it: once the bar's rule has a border, Qt paints the bar from
    the stylesheet instead of handing it to the native style. A drop-down
    with a border is likewise no longer painted natively, so its background
    is stated beside it (`palette(window)`), or the items could come out with
    no panel behind them.

    Once an item rule draws a background, Qt stops handing items to the
    native style, hover and selection included, so the selected colors are
    stated here too. `highlight` and `highlighted_text` are a selected item
    in a drop-down and an open title on the bar; they default to the
    palette's `Highlight` and `HighlightedText`, so the menus follow the
    desktop the way the unstyled ones did. `hover` is a title on the bar
    under the mouse but not yet open, painted as a background only, so the
    title keeps its own text color; left out, hover is the full highlight.

    The highlight is written for `:selected:enabled`, so a disabled item the
    mouse is over is left exactly as it was. Overriding a `:selected` rule
    with `:disabled:selected` clears the background but not the text color,
    which turns a hovered disabled item bright as if it could be chosen.

    The `min-width` is on the item, not the menu: a width on QMenu widens
    the frame but leaves the items, and their highlight, at their natural
    width.

    `point_size` sets the font of the bar and its menus, and is left to the
    widgets' own font when omitted.
    """
    highlight = _css_color(highlight if highlight is not None else "palette(highlight)")
    highlighted_text = _css_color(
        highlighted_text if highlighted_text is not None else "palette(highlighted-text)"
    )
    selected = f"background: {highlight}; color: {highlighted_text};"
    hovered = f"background: {_css_color(hover)};" if hover is not None else selected
    font = f" font-size: {point_size}pt;" if point_size is not None else ""

    return f"""
        QMenuBar {{{font}
            padding: {MENU_BAR_PADDING};
            border-bottom: {DIVIDER_BORDER};
        }}
        QMenuBar::item {{ padding: {MENU_BAR_ITEM_PADDING}; background: transparent; }}
        QMenuBar::item:selected {{ {hovered} }}
        QMenuBar::item:pressed {{ {selected} }}
        QMenu {{{font}
            padding: {MENU_PADDING};
            background: palette(window);
            border: {DIVIDER_BORDER};
        }}
        QMenu::item {{
            padding: {MENU_ITEM_PADDING};
            min-width: {MENU_ITEM_MIN_WIDTH}px;
            background: transparent;
        }}
        QMenu::item:selected:enabled {{ {selected} }}
    """


def apply_menus(
    *widgets,
    highlight: QColor | str | None = None,
    highlighted_text: QColor | str | None = None,
    hover: QColor | str | None = None,
    point_size: int | None = None,
) -> None:
    """Give each menu bar, or standalone menu, the shared menu styling.

    Set on a QMenuBar, the sheet reaches its drop-downs and their submenus
    too: a QMenu made by `addMenu(title)` is the bar's (or the menu's)
    child. A QMenu built on its own — a context menu, or one handed to
    `addMenu(menu)` — is not, and is passed here itself.

    The sheet is built once and set on every widget passed, and nothing is
    kept: no reference to any widget, and nothing set on the application.
    The keyword arguments are passed straight through to `menu_style()`.
    """
    sheet = menu_style(
        highlight=highlight,
        highlighted_text=highlighted_text,
        hover=hover,
        point_size=point_size,
    )
    for widget in widgets:
        widget.setStyleSheet(sheet)
