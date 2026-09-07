# Notes to AI Agents

## What this is
This is a library that takes care of application window and dialog styling so that we can share it across all our Python projects. Several unrelated things live here: the colored title bar, a markdown viewer for showing an app's own `docs/` inside itself, the wide scroll bars the apps use everywhere, and two widget looks the apps share — the enlarged radio indicator and the on/off toggle switch.

## Modules

- `theme.py` — `ChromeTheme`, the colors and the Wayland decoration plugin name, plus the module-level active theme.
- `titlebar.py` — `configure()` / `install()` and the body-color accessors. Order-sensitive and Wayland-only; README §4 and §6 are the contract.
- `markdownview.py` — `MarkdownView`, a `QTextBrowser` that adds navigation and image fitting to what Qt already renders. Separate from the dialog on purpose: markdown is not always shown in one.
- `markdowndialog.py` — `MarkdownDialog`, `show_markdown()` and `close_markdown_windows()`: a modeless window around a view, with a registry so a document opens once.
- `scrollbars.py` — `scrollbar_style()` and `apply_scrollbars()`, the bars drawn at twice the desktop's own thickness. Self-contained: no setup, no platform requirement, nothing shared with the other two. README §9 is the contract.
- `radiobuttons.py` — `radio_style()` and `apply_radios()`, the enlarged, visibly outlined radio indicator. Self-contained in exactly the way `scrollbars.py` is, down to the `base` argument meaning the same thing. README §10 is the contract.
- `toggleswitch.py` — `ToggleSwitch`, a checkable `QAbstractButton` painted as a track with a sliding knob, for where a check box would have gone. The one shared look here that is a *widget* rather than a stylesheet, because the shape differs and not just the size and color; a stylesheet cannot slide a knob. Self-contained like the two above. README §11 is the contract.

**`scrollbars.py` and `radiobuttons.py` read `QPalette.Base` (and `Text`) straight from the application palette, and that is not the gotcha-3 mistake.** Gotcha 3 forbids deriving a *body* color from `QApplication.palette()` because `install()` repurposes `Window` and `WindowText` for the title bar. Neither `Base` nor `Text` is one of them, so reading them here is correct and routing it through `body_window_color()` would be wrong. Don't "fix" it. `toggleswitch.py` reads neither: its off track and knob are pinned grays, because `Base` is the pane the switch sits *on* and a switch painted in it would vanish — that is a decision, not an oversight (README §11).

**The view never modifies the document it is showing, and that is the constraint the design rests on.** It renders what Qt renders — no restyling, no injected anchors. Several hundred format changes to a document being laid out incrementally stops the layout part way through, and a whole section renders as a band of blank space with the text present but invisible. If you are tempted to add a theme-aware link color or a code-block background, that is the price; read README §5 first. `test_the_document_is_never_modified` is the guard.

**Read README §5 before touching either markdown module.** Every rule in it was measured, and most of them look like something worth simplifying until you know why they are there.

## Tests

```bash
./tests/run.sh                              # everything, ~1s
./tests/run.sh tests/test_markdownview.py   # one file
./tests/run.sh -k anchor -v                 # by name
```

`run.sh` pulls pytest and pytest-qt in with `uv run --with`, so nothing is declared in `pyproject.toml` and there is no install step. Fixtures build their documents into `tmp_path` rather than checking them in.

Two things that will waste your time otherwise: under `QT_QPA_PLATFORM=offscreen` a widget that was never shown and resized has no layout, so every scroll bar reads 0 and every "did it scroll" assertion passes vacuously — use the `shown` fixture. And never hand a `MarkdownDialog` to `qtbot.addWidget`: it sets `WA_DeleteOnClose` and deletes itself, so pytest-qt's teardown reaches for a widget that is gone and fails the *following* test.

## Working in this repo

* Do not commit changes to 'git' repository, or offer to. Only the Human developer will do commits.
