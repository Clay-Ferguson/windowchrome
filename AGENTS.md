# Notes to AI Agents

## What this is
This is a library of shared widget styling and GUI pieces, so that we can share it across all our Python projects. Several unrelated things live here: a markdown viewer for showing an app's own `docs/` inside itself, the wide scroll bars the apps use everywhere, and three widget looks the apps share — the enlarged radio indicator, the enlarged check-box indicator and the on/off toggle switch.

**There is deliberately no window chrome here.** This library used to color the title bar and window frame, by choosing Qt's `bradient` Wayland decoration plugin and repurposing the application palette's `Window`/`WindowText` roles and the application font for it, then handing them back to every widget through an application-wide event filter. It was removed as too fragile — it rested on undocumented plugin internals and leaked into every consuming app. Do not reintroduce it, or anything else that needs a setup call around `QApplication` construction.

## Modules

- `markdownview.py` — `MarkdownView`, a `QTextBrowser` that adds navigation and image fitting to what Qt already renders. Separate from the dialog on purpose: markdown is not always shown in one.
- `markdowndialog.py` — `MarkdownDialog`, `show_markdown()` and `close_markdown_windows()`: a modeless window around a view, with a registry so a document opens once.
- `scrollbars.py` — `scrollbar_style()` and `apply_scrollbars()`, the bars drawn at twice the desktop's own thickness. Self-contained: no setup, no platform requirement. README §9 is the contract.
- `radiobuttons.py` — `radio_style()` and `apply_radios()`, the enlarged, visibly outlined radio indicator. Self-contained in exactly the way `scrollbars.py` is, down to the `base` argument meaning the same thing. README §10 is the contract.
- `checkboxes.py` — `apply_checkboxes()` and the `LargeIndicatorStyle` under it, the check-box indicator drawn at twice the desktop's size. Self-contained like the two above, but a `QProxyStyle` rather than a stylesheet, and *that is the entry's whole point*: a `QCheckBox::indicator` rule setting only `width`/`height` does work — but add a `border` or a `background` to it and Qt stops delegating to the native style, and since no CSS property draws a check mark the box renders empty and a checked box stops looking checked. The proxy never leaves the native drawing path, so it cannot fall off that edge. The radio helper goes the stylesheet route because a circle *is* drawable in CSS. Do not "unify" the two. Note also that `box.style()` may not hand the proxy back — a stylesheet anywhere up the ancestor chain puts Qt's own `QStyleSheetStyle` in front of it, so assert on the metric or on `findChildren(LargeIndicatorStyle)`, never on `style()`'s type. README §12 is the contract.
- `toggleswitch.py` — `ToggleSwitch`, a checkable `QAbstractButton` painted as a track with a sliding knob, for where a check box would have gone. The one shared look here that is a *widget* rather than a stylesheet, because the shape differs and not just the size and color; a stylesheet cannot slide a knob. Self-contained like the others above. README §11 is the contract.

**`toggleswitch.py`'s off track and knob are pinned grays, not palette colors, and that is a decision rather than an oversight.** `Base` is the pane the switch sits *on*, so a switch painted in it would vanish (README §11). `checkboxes.py` reads no palette color at all — the native drawing it keeps already follows the theme, and only the size was ever wrong.

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
