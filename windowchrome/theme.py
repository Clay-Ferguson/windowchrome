"""The colors and dimensions windowchrome paints with."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChromeTheme:
    """One application's chrome, as data.

    `decoration` is a Qt Wayland decoration *plugin name*, not a desktop theme
    name. Only `bradient` reads the application palette; `adwaita`, the Qt
    default, has its colors compiled in. An unknown name falls back to
    `adwaita` silently, which is why `install()` warns about a mismatch.
    """

    title_bg: str = "#1e3a5f"
    title_fg: str = "#ffffff"

    #: The title text while the window is *not* the active one — which on
    #: Wayland includes the whole of an interactive move, since dragging the
    #: bar takes keyboard focus away and `bradient` then paints from the
    #: palette's `Disabled` group. Defaulting it to `title_fg` is what keeps
    #: the title legible and, more to the point, *unchanging*: a color that
    #: dims the moment the window is picked up reads as the window breaking
    #: rather than as a focus cue. Set it to something dimmer to get the
    #: conventional inactive look back.
    title_fg_inactive: str = "#ffffff"

    #: The weight the title is drawn at — a `QFont` weight, so 400 is normal,
    #: 700 bold, 900 black; any integer in between works too. Bold by default:
    #: the bar is a colored band with one piece of text on it, and 14px of
    #: regular-weight type is thin against it.
    #:
    #: **The title's *size* is not reachable from here, and cannot be.**
    #: `QWaylandBradientDecoration::paint()` does `font.setPixelSize(14)` on
    #: the painter's font with 14 compiled in (`mov $0xe,%esi` right before the
    #: call, in the shipped plugin), so whatever point size the application
    #: font carries is discarded. Weight, stretch, family and italic survive
    #: because the plugin overwrites none of them. `title_font_stretch` is the
    #: only lever left in the direction of "bigger".
    title_font_weight: int = 700

    #: How wide the title's glyphs are drawn, as a percentage: 100 leaves the
    #: font alone, 115 widens it by 15%. The one dimension of "larger" the
    #: hardcoded 14px pixel size above leaves open. Off by default, since a
    #: stretched face is a real typographic choice rather than a free win.
    title_font_stretch: int = 100

    decoration: str = "bradient"


DEFAULT_THEME = ChromeTheme()

# The active theme is module state rather than an object the host passes
# around: it is one application-wide look, and threading it through every
# dialog constructor would be plumbing with no decision in it.
_active: ChromeTheme = DEFAULT_THEME


def set_theme(new: ChromeTheme) -> None:
    global _active
    _active = new


def theme() -> ChromeTheme:
    return _active
