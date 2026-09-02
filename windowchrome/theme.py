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
    title_fg_inactive: str = "#8fa1b8"
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
