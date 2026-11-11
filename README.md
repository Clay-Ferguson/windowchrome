# windowchrome

This project is a dependency that's required by Sonar, Start Menu, Postit, and Lingo which are the four PyQt6 apps available under the 'clay-ferguson' github repositories. To use any of those four applications you'll need to have this project in a sibling folder next to those folders

This package does six unrelated things for a PyQt6 application on Linux:

1. **A markdown viewer** (§5), so an app can show its own documentation — whatever is in its `docs/` folder — inside itself, with working links and images.
2. **Wide scroll bars** (§9), about twice the thickness the desktop draws, so they are easier to grab with the mouse. Per scroll area, opt-in, and self-contained.
3. **Radio buttons** (§10) with an enlarged, visibly outlined indicator, in place of the small near-black one the desktop draws. Per button, opt-in, and self-contained in the same way.
4. **A toggle switch** (§11) — a track with a sliding knob, to put where a check box would have gone. A widget you construct rather than a style you apply, and self-contained in the same way.
5. **Check boxes** (§12) with an enlarged indicator, keeping the tick Qt draws. A style rather than a stylesheet, for the reason §12 gives. Per box, opt-in, and self-contained in the same way.
6. **A title bar and window frame** (§13) drawn by the app itself — a navy title bar and a gray border in place of the system's. One call per top-level window, opt-in, and self-contained in the same way.

None of them needs a setup call, an ordering rule around `QApplication`, or any particular platform. Written for an AI agent integrating it into an existing app: §3 covers installation, and each of §5, §9, §10, §11, §12 and §13 is self-contained.

**The window frame (§13) replaces an earlier one, and is built differently on purpose.** This library used to color the system's own title bar, by choosing Qt's `bradient` Wayland decoration plugin and repurposing application palette roles and the application font for it, handed back to every widget through an application-wide event filter. That was removed as too fragile — it rested on undocumented plugin internals and leaked into every consuming app. §13 draws its own frame on a frameless window with documented Qt API only, touches nothing application-wide, and depends on no decoration plugin. Do not bring back any part of the old approach.

The numbering is historical: the sections that described the old title bar (§1, §4, §6, §7) are gone, and the rest keep their numbers because the consuming apps cite them from their own `AGENTS.md`.

---

## 2. Requirements

- PyQt6 (≥ 6.6). No other dependency.
- No platform requirement: nothing here depends on Wayland, X11 or the window manager. §13 is written for Wayland and tested by hand only there, but uses no platform-specific API, so it works under X11 too.

## 3. Installation

`windowchrome` is **not published to PyPI**. Clone it from GitHub and consume it from a **sibling directory** of the project using it — the sibling relationship is what makes the `../windowchrome` path below resolve, so the directory has to be named this and has to sit beside the consumer:

```bash
cd ..                      # the directory holding your-app/
git clone https://github.com/<your-account>/windowchrome.git
```

```
projects/
├── windowchrome/     <- this repo
└── your-app/
```

In the consumer's `pyproject.toml`:

```toml
dependencies = [
    "PyQt6>=6.6",
    "windowchrome",
]

[tool.uv.sources]
windowchrome = { path = "../windowchrome", editable = true }
```

`editable = true` is what makes side-by-side development work: the clone is used in place, so there is nothing to build and an edit here is picked up by every consumer on its next run, with no reinstall. If the sibling checkout is missing, `uv run` fails with an unresolved path dependency rather than with anything subtle.

A consumer that is itself not an installable package keeps its own `[tool.uv] package = false`; that governs the consumer and does not conflict with the source above.

## 5. The markdown viewer

No setup and no platform requirement. Two names do the whole job.

```python
from windowchrome import show_markdown

show_markdown(
    docs_dir / "USER_GUIDE.md",
    parent=main_window,
    title="Sonar — User Guide",
    button_factory=lambda text: action_button(text, uniform=True),
)
```

and, from the host's main window `closeEvent`:

```python
from windowchrome import close_markdown_windows
close_markdown_windows()
```

`show_markdown()` returns the dialog. `MarkdownView` is the widget on its own, for markdown shown somewhere that is not a dialog — which is why the rendering does not live inside `MarkdownDialog`.

`title` names the document the window is opened on. Anything navigated to from there is named by its own first heading instead — a window that can follow a link cannot keep the title it opened with, or it ends up headed "Query Syntax" while showing the user guide.

### What Qt gives you, and what it does not

Qt renders markdown itself: `QTextBrowser.setMarkdown()` and `setSource(url, MarkdownResource)` handle headings, tables, fenced code, blockquotes, task lists, links and images. **No markdown package is a dependency and none should become one.** Measured on a real 632-line document: 21268 characters, 30 headings, 12 tables, 27 fenced code blocks.

Qt's own history is enough, too. `setSource` → navigate → `backward()` returned to the first document **and restored the scroll bar to the exact value it was left at** (2897). So there is no history stack in this library and no scroll bookkeeping: `backward()`, `isBackwardAvailable()` and the `backwardAvailable(bool)` signal are the whole of it, and the last drives the Back button's `setEnabled` directly.

What Qt does not do is give headings anchor names, so a `[Contents](#contents)` link has nothing to scroll to, and it does not fit an image to the view. That is the entire gap, and both are closed without changing the document.

### The rule everything else follows from: never modify the document

**This view renders what Qt renders.** It does not restyle it. There is no theme-aware link color and no code-block background, and that is a decision rather than an omission.

An earlier version had both, plus injected heading anchors, and the cost was out of all proportion. Each was a pass over the rendered document merging a format per fragment or per block — several hundred changes. Applied to a document Qt is laying out *incrementally*, which is what happens whenever the widget is already on screen when the content arrives, the layout stops part way through: every block past that point keeps a height of **zero**. On screen that is a run of paragraphs rendering as a band of blank space — text present, selectable and copyable, but invisible and occupying almost no height. Measured on the 632-line guide: 73 of its 302 paragraphs never laid out, and the document reported itself 5338px tall instead of 7480.

Batching the changes into one `beginEditBlock()`/`endEditBlock()` did fix it. The better answer was to stop making them:

- **Fragment links do not need anchors in the document.** `scroll_to_heading()` reads the headings, matches the slug, asks the layout where that block sits, and sets the scroll bar. Nothing is written. It works from `sourceChanged` too, before Qt has laid out the rest, because asking for a block's rectangle lays the document out as far as that block. It also deletes a failure mode outright: injected anchors had to be re-applied after every `backward()`, since that re-renders; found headings never need re-applying.
- **The link color is Qt's.** For the record, it cannot be changed *except* by modifying the document: the importer sets an explicit `ForegroundBrush` of `#0000ff` on every link fragment, and `QPalette.Link` is ignored — verified by pixel-sampling a render with the role set to red and to green, which painted identical blue. A host that truly needs a different link color on a dark background is asking for the pass that broke the layout; weigh it against that.
- **Code blocks are monospace, with no background band.** Cosmetic, and not worth touching the document for.

The one piece of appearance that *is* set here is the white space around the text, and it is set without touching the document: `DOCUMENT_MARGIN` (20px, up from Qt's 4) goes onto the document's root frame in the view's constructor, before anything is loaded. Qt's default puts the first character hard against the frame and the longest line hard against the scroll bar, which reads as broken rather than as plain. A margin is a property *of* the document rather than a change *to* it — no format merges, no relayout of blocks already laid out — and, measured, it survives `setSource`, `backward()` and `set_markdown()` without being re-applied and leaves `isModified()` false, so `test_the_document_is_never_modified` still holds.

Two things scale with it, and are why it is a named constant rather than a number in a constructor: `loadResource`'s viewport fallback subtracts it from both sides, and `MarkdownDialog.CONTENT_INSET` is written as `60 + 2 * DOCUMENT_MARGIN`. Widen the margin without those and images start overflowing into a horizontal scroll bar.

`MarkdownView` therefore implements exactly two things, and both are places Qt asks a subclass to fill in rather than places it has to be reached into:

**1. `loadResource()` — image fitting.** Qt does not read image files itself: it calls `loadResource` during layout, **before the first paint**, and lays out whatever comes back at the size it comes back. So returning an already-scaled `QImage` is the whole of fitting one — no walking the document afterwards rewriting `QTextImageFormat` widths, no second layout pass, no flash of an oversized image. Measured with a 1153×935 screenshot in a 684px viewport: without it, horizontal scroll bar 477 and a 1161px document; with it, scroll bar **0** and a 682px document, on the first render.

Two details that are not obvious. The base implementation returns the file's raw bytes as a **`QByteArray`**, not an image, so decoding them is not optional. And scaling is **down only** — a small inline icon is already the size it wants to be.

The dialog pins its `minimumWidth` to the width it fitted images to. That is what makes "one render" true for the life of the window: measured, dragging narrower than the fitted width brings the overflow back (a 420px window put the scroll bar at 278), and the only cure would be dropping the image cache, re-rendering, and restoring the scroll position. Pinning the minimum means that path does not exist. Widening is free — an image stays its size rather than upscaling, which is right for a screenshot.

**2. Link handling.** `setOpenLinks(False)` and an `anchorClicked` handler, because Qt's own is unsafe here:

- **Nothing reaches `setSource` that has not been stat'd.** `setSource` does not fail on a URL it cannot load: measured, an `https://` URL and a missing local file each left the document at **1 character** and still pushed a history entry, and `setOpenExternalLinks(True)` did not prevent it — that flag is only consulted on the click path. A click on a target that does not exist does nothing, which is a better outcome than a blank window.
- **An in-page link scrolls; it never calls `setSource("#x")`.** With a source already set, `#x` resolves *against it* and reloads: measured, 21268 → 23149 characters and the scroll bar did not move.

Slugs are GitHub's rule over the *rendered* block text, `-1`/`-2` for repeats. Rendered, not source: the importer has already eaten the backticks, so `` ## `search.included` `` arrives as `search.included` and slugs to `searchincluded`, which is what GitHub produces for the same heading — so a link written against the file on GitHub resolves against the file in the widget. `heading_slugs()` is exported for exactly one reason: anything that *checks* a document's links must number repeats identically, and a checker with its own copy of the rule is one that will eventually disagree with the view.

`test_the_document_is_never_modified` asserts `document().isModified()` is false after loading and navigating. That is the guard on all of the above: any styling pass that creeps back in has to modify the document, and would fail it.

### Buttons, and why there is a factory

The dialog owns no look beyond its layout. The four applications using this library each build a button differently — a colored free function, a stylesheet constant on a `QDialogButtonBox`, a method on the main window that wires the slot too, and a `QToolButton` — so there is no convention to standardise on here. `button_factory` is the narrowest seam all of them can satisfy, and it is typed `Callable[[str], QAbstractButton]` because of that last one.

Without a factory the buttons are bare `QPushButton`s wearing the desktop theme, deliberately: an integration that forgets is one that looks wrong immediately rather than looking almost right forever.

`.view` and `.button_row` are public for the styling a factory cannot reach — a host that widens its scroll bars everywhere calls `apply_scrollbars(dlg.view)` (§9) on what `show_markdown()` hands back. The dialog does not call it itself: the wide bars are a host's decision, and an app that has not made it should not have them appear in its help window alone.

### The registry, and the two ways a dialog dies

Windows are modeless and kept in a module-level dict keyed by the resolved path, so asking for a document twice raises the window already showing it. Eviction is the subtle part, and it is measured:

- **A dismissed dialog must be evicted synchronously.** `close()`, `reject()` and Escape all emit `finished` immediately, but deletion is a `deleteLater` that lands on a later turn. Evicting only on `destroyed` leaves a dialog that is on its way out still registered — so the next open "raises" it and hands back a window that vanishes a moment later. Hence `finished`, with `destroyed` kept as the backstop for a dialog torn down without being closed.
- **Eviction compares identity, and never calls a method on the dialog.** `destroyed` arrives a turn late: close A, open B for the same path, and A's notification lands with B already registered. Without `_WINDOWS.get(key) is dialog`, B is evicted and a third open stacks a duplicate. The check is a Python wrapper comparison, which is also the only kind that is safe from a `destroyed` handler — by then the C++ object is gone and touching it raises.
- `close_markdown_windows()` iterates a **copy**, because each close mutates the dict.

**A parented modeless dialog does not hold the application open.** It has a transient parent, so it is not a "primary" window and `quitOnLastWindowClosed` still fires — measured, the app quit with a help window visible. But that window *is* still on screen for as long as that takes, so a host should still call `close_markdown_windows()` from its main window's `closeEvent`. An *unparented* window is a different story and would keep the process alive.

## 8. Troubleshooting

**The markdown viewer:**

| Symptom | Cause |
| --- | --- |
| The help window is blank, or one character long | Something handed `setSource` a URL that is not an existing local file. It does not fail; it renders nothing and pushes a history entry. Stat first — see §5 rule 2. |
| A Contents link does nothing | A heading was renamed, so its slug moved with it. `scroll_to_heading()` returns False when no heading matches. |
| A band of blank space mid-document; the text is there if you select and copy it | Something modified the document, and an incremental layout stopped part way through. The view must never write to it — see §5. |
| A wide screenshot scrolls sideways | `loadResource` was overridden without decoding the `QByteArray` the base class actually returns, or the window's `minimumWidth` was not pinned to the width images were fitted to. |
| Links are blue and hard to read on a dark background | Qt's color, and it cannot be changed without modifying the document. See §5. |
| Re-opening a document gives a window that vanishes | The registry is evicted only on `destroyed`. A dismissed dialog is still registered until its `deleteLater` runs — evict on `finished`. |
| `RuntimeError: wrapped C/C++ object has been deleted` | Something called a method on a registered dialog after it was dismissed, or eviction compares with `==` rather than `is`. |
| The app does not exit after its main window closes | Only possible with an *unparented* window: it becomes a primary window. Parent the dialog, and call `close_markdown_windows()` from `closeEvent`. |

**The window frame (§13):**

| Symptom | Cause |
| --- | --- |
| The system title bar is still there, above the drawn one | `apply_frame()` ran after the window was shown on a platform that cannot change a live window's flags, or not at all. Call it before the first `show()`. |
| The app's content overlaps the title bar | Something set the *window's* contents margins after the frame did, or the content was positioned by hand rather than by a layout. The frame owns the window's margins; put margins on the layout instead. |
| A dialog's title bar is the system's | That dialog was not handed to `apply_frame()` — typically a static `QMessageBox.critical()` call. Build the box, frame it, then `exec()` it. A desktop file chooser keeps the system's bar by design. |
| No resize cursor at an edge | The window is maximized or fullscreen, or fixed in that axis (`setFixedSize()`; a `QMessageBox` always is). |
| A crash, or `wrapped C/C++ object … has been deleted`, painting a title bar | Something in the frame holds a reference to its window, so the window is freed by the cycle collector at an arbitrary moment. See §13. |

---

## 9. Wide scroll bars

A desktop's own scroll bar is a few pixels wide and fiddly to hit with a mouse. `scrollbar_style()` returns a Qt stylesheet drawing one at `SCROLLBAR_SCALE` (2) times that, and `apply_scrollbars()` puts it where it goes:

```python
from windowchrome import apply_scrollbars

apply_scrollbars(self.results)                       # a QAbstractScrollArea
apply_scrollbars(self._text_edit, field_background)  # ... painted some other color
```

Nothing to call before or after the `QApplication`, and no platform requirement. It is opt-in per scroll area rather than an application-wide stylesheet, because an application-wide one would sever palette inheritance across every widget in the app to change two.

Four things about it are deliberate, and each looks like something worth simplifying until you know why:

- **The thickness is read, not assumed.** `QApplication.style().pixelMetric(PM_ScrollBarExtent)` is what the desktop would have drawn; the style doubles *that*, floored at `MIN_SCROLLBAR_EXTENT` (12) in case a style reports something implausibly small or nothing at all. A fixed pixel count would be double on the one theme it was measured against and wrong on the next.
- **The steppers have to be described.** Styling a scroll bar at all opts it out of native drawing, so the groove, the handle *and* both stepper buttons become this stylesheet's problem. `add-line`/`sub-line` are explicitly collapsed to zero size: left undescribed they render as blank boxes at each end. Zero-sized steppers also give the handle the whole length of the bar, which is the point of the extra width.
- **The contrast goes both ways.** The handle is `base.lighter(230)` on a dark pane and `base.darker(140)` on a light one, chosen by `base.lightness() < 128`, with hover a further step in the same direction. A single pinned gray suits exactly one of the two themes.
- **The stylesheet goes on the two `QScrollBar` children, never on the scroll area.** The area keeps its native rendering and only the bars change.

A host that wants a particular handle color — to match another toolkit's bars, say — passes `handle=` as well; the hover is still derived from it, a step further from `base`. Leave it out and the handle follows `base` as above, which is the right default: a pinned gray suits one theme.

```python
apply_scrollbars(self.tree, handle="#777777")
```

### The `base` argument

`base` is the color the bar sits *in*; the groove is painted with it so the bar reads as part of the pane rather than as a stripe laid over it. It defaults to the palette's `Base`, which is what a pane normally is. A host that paints its field some other color — one *derived* from `Base`, say — passes that color instead, or the groove shows through as a visibly different shade against the field:

```python
field = QApplication.palette().color(QPalette.ColorRole.Base).lighter(130)
edit.setStyleSheet(f"background-color: {field.name()};")
apply_scrollbars(edit, field)
```

---

## 10. Radio buttons

The native radio indicator is small — around 13px — and rings itself in a near-black that all but disappears against a dark dialog. `radio_style()` returns a Qt stylesheet drawing a bigger one in a color that shows, and `apply_radios()` puts it on the buttons:

```python
from windowchrome import apply_radios

apply_radios(self._file_radio, self._sh_radio,
             base=field_background, point_size=UI_POINT_SIZE)
```

Like the scroll bars (§9): nothing to call before or after the `QApplication`, no platform requirement, and opt-in per widget rather than an application-wide stylesheet that would sever palette inheritance everywhere.

Three things about it are deliberate:

- **The whole indicator has to be described.** Styling `::indicator` at all opts the button out of native drawing, so the circle, its ring and the checked state are all this stylesheet's problem. There is no "keep the native dot, just bigger".
- **The checked state is a filled circle, not a ring with a dot in it.** A stylesheet element has one border, so a gap between the ring and an inner dot cannot be drawn without giving up the ring — and the ring is what makes the *unchecked* state visible at all. At `RADIO_INDICATOR_SIZE` (22px) a solid fill is unambiguous.
- **The ring and the fill come from the palette's `Text`.** So the indicator reads as bright as the label beside it, and follows the desktop between a light theme and a dark one instead of pinning a gray that suits one of them.

`base` is the color painted inside an unchecked circle — the same argument, with the same reasoning, as the scroll bars' `base` (§9). It defaults to the palette's `Base`; a host whose dialog fields are painted some color derived from `Base` passes that instead. `point_size` sets the label's font size, and is left to the widget's own font when omitted.

---

## 11. The toggle switch

Where a setting is on or off and the app wants to *say* so — a mode you can see from across the room — `ToggleSwitch` draws the switch a phone's settings screen draws: a rounded track with a knob that slides to the far end when it is on.

```python
from windowchrome import ToggleSwitch

self.edit_toggle = ToggleSwitch(self, on_color=HIGHLIGHT_BG)
self.edit_toggle.toggled.connect(self._handle_edit_toggled)
```

Like the scroll bars (§9) and the radio buttons (§10): nothing to call before or after the `QApplication`, and no platform requirement.

Three things about it are worth knowing:

- **It is a painted widget, not a stylesheet.** The other two helpers are stylesheets because what was wrong with the native widget was its size and its color. Here the *shape* is wrong: a check box indicator is a square with a tick in it, and no stylesheet moves a knob from one end of a track to the other. Qt's own route would be a pair of images swapped on toggle, which pins the colors into files. A checkable `QAbstractButton` with its own `paintEvent` is a dozen lines and follows whatever colors it is handed.
- **It is still the button it inherits from.** `isChecked()`, `setChecked()`, `toggle()`, `toggled`/`clicked`, Space to flip it, and the focus and tab behavior are all `QAbstractButton`'s. Only the painting is this library's, so a host swapping a `QCheckBox` for one changes the constructor and nothing else. It has no label of its own — put a `QLabel` beside it, which is what a settings row wants anyway.
- **Its size is fixed, not laid out.** `TOGGLE_WIDTH`×`TOGGLE_HEIGHT` (40×22) by default, overridable per switch with `width=`/`height=`. A layout that stretched the track would not stretch the knob's travel with it, and the travel is what reads as a switch.

`on_color` is the track while checked — the host's accent, and the one argument worth passing; it defaults to the palette's `Highlight`. `off_color` (`#888888`) and `knob_color` (`#ffffff`) are pinned rather than taken from the palette: `Base` is the pane the switch is sitting on, so a switch painted from it would disappear into its background. Both are overridable. All three take a `QColor` or anything `QColor` accepts, since a host's accent is usually already a `"#rrggbb"` constant.

---

## 12. Check boxes

The native check box indicator is around 13px — sized for a mouse that never misses. `apply_checkboxes()` draws it at `CHECKBOX_SCALE` (2) times that, and changes nothing else about the widget:

```python
from windowchrome import apply_checkboxes

apply_checkboxes(self.wrap_check, self.archive_check)
```

Like the scroll bars (§9), the radio buttons (§10) and the toggle switch (§11): nothing to call before or after the `QApplication`, no platform requirement, and opt-in per widget rather than an application-wide style.

Three things about it are deliberate:

- **It is a `QProxyStyle`, not a stylesheet, and that is not an oversight.** A stylesheet `QCheckBox::indicator { width: …; height: … }` does work: geometry is all it sets, so `QStyleSheetStyle` applies the size and still lets the native style paint the box and its tick. It works only while the rule stays geometry, though — add a `border` or a `background` and Qt takes the drawing to be yours, stops delegating, and paints only what the rule names. No CSS property draws a check mark (Qt's answer is `image: url(tick.png)`, i.e. images for every state), so the indicator renders empty and a checked box stops looking checked. Measured: `width`/`height` alone keeps the tick, `border: 2px solid #444` loses it. The proxy exists because that failure is silent and one word away — overriding the pixel metric changes the rectangle the native style is handed and never leaves the native drawing path. `radio_style()` (§10) goes the stylesheet route because a circle *is* drawable in CSS and a tick is not.
- **Only `PM_IndicatorWidth`/`PM_IndicatorHeight` are answered; every other metric is forwarded.** A style that scaled anything else would grow the widget's spacing and frames along with the box. `PM_ExclusiveIndicatorWidth` — the *radio* indicator — is among the metrics left alone, so the two helpers do not overlap. `test_every_other_metric_is_left_alone` is the guard.
- **A style is built per box and parented to it.** Not one shared instance and not `QApplication.setStyle()`: this is one widget's affordance, not a change of theme. The parenting is also load-bearing — `setStyle()` does not take ownership, so a style with no parent is collected out from under a live widget and crashes it.

One thing to know before writing a test or debugging one: **`box.style()` does not necessarily hand this style back.** As soon as any ancestor widget carries a stylesheet, Qt slips its own `QStyleSheetStyle` in front of the widget's style and `style()` returns *that*. The metric still comes through it — the indicator is drawn at the enlarged size either way — but an `isinstance` check against `LargeIndicatorStyle` passes on a bare check box and fails on the same box inside a real window. Ask the box for the metric, or for `findChildren(LargeIndicatorStyle)`, and not for `style()`'s type.

Nothing here reads the palette, unlike §9 and §10: the native drawing already follows the theme, and only the size was ever wrong. `LargeIndicatorStyle` is exported for a host that wants the style object itself — to hand to a widget `apply_checkboxes()` does not cover, say — but the applier is the interface.

Where a check box is the wrong *shape* rather than the wrong size — an on/off setting the app wants to state loudly — `ToggleSwitch` (§11) is the other answer.

---

## 13. The window frame

The system title bar on GNOME under Wayland is drawn by a Qt decoration plugin (`adwaita` or `bradient`) with no color setting, and on a dark theme it comes out as dark as the window's own background, so nothing separates the window from its contents. `apply_frame()` hides it and draws one of the app's own: a title bar with the title centered and minimize, maximize and close buttons on the right, and a 2px border round the whole window.

```python
from windowchrome import apply_frame

window = MainWindow()
apply_frame(window)        # once, before the window is first shown
window.show()
```

```python
box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=self)
apply_frame(box)           # a dialog: a close button only
box.exec()
```

Like §9–§12: nothing to call before or after the `QApplication`, no platform-specific code, and opt-in one window at a time. It takes any top-level `QWidget` — a plain one with a layout, a `QMainWindow`, a `QDialog`, or a `QMessageBox` built as an instance (the static `QMessageBox.critical()` and friends build and run their box in one call, so there is nothing to hand it; a host wraps them in a helper that builds the box, frames it and runs it).

### What it looks like

| Part | Active window | Inactive window |
|---|---|---|
| Title bar | `#1e3a5f` | `#112238` |
| Title and button glyphs | `#ffffff` | `#8fa1b8` |
| 2px line along the bar's bottom, inside it | `#2c6dbc` | `#1c3d5a` |
| Border, 2px | `#777777` | `#777777` |

These are `FrameColors`' defaults, taken from a GTK theme's CSS so a Qt window's frame matches the GTK apps beside it. Inactive is GTK's `:backdrop` — another window has focus — and follows Qt's window activation. The buttons light to `#2d5282` under the mouse and `#2c6dbc` while pressed; close turns red (`#c01c28`, pressed `#a51d2d`) with a white glyph. Override any of them:

```python
apply_frame(window, FrameColors(title_bg="#3b2a1e", title_line="#bc6d2c"))
frame.set_colors(...)      # later, on the WindowFrame apply_frame returned
```

The title bar's height comes from its (bold) font, at least `TITLE_BAR_MIN_HEIGHT` (36). The title is centered in the space left of the buttons and elided if it doesn't fit, and follows `setWindowTitle()`. A `QDialog` (so a `QMessageBox` too) gets only a close button, as a dialog does on GNOME; `minimize=`/`maximize=` override that either way. Without a maximize button, double-clicking the bar does nothing.

| Action | Result |
|---|---|
| Drag the title bar | Moves the window (`QWindow.startSystemMove()`), once the mouse has moved the desktop's drag distance |
| Double-click the title bar | Maximize / restore |
| Drag within 8px of an edge, 16px of a corner | Resizes (`QWindow.startSystemResize()`), with the matching cursor |
| Maximized | No border, no resize zones; the title bar stays, and the maximize button shows a restore glyph |
| Fullscreen | No border, no resize zones, no title bar |

### How it is built, and why this way

Everything is attached to the one window it was handed. There is no event filter on `QApplication`, no application palette or stylesheet change, and nothing reaches into a decoration plugin — the three things that sank the old title-bar code (see the top of this README).

- **The window is made frameless** with `Qt.WindowType.FramelessWindowHint`, so no decoration plugin draws anything and nothing here depends on how one works inside.
- **The window stays the window, and the frame lives inside it.** `apply_frame()` sets the window's own contents margins: `FRAME_BORDER_WIDTH` (2) on every side, plus the title bar's height on top. Qt lays a layout out inside its widget's contents rectangle, so the app's layout — a `QMainWindow`'s menu bar, or a menu bar given to `QLayout.setMenuBar()` — lands below the title bar and inside the border with no change to the app's code. The title bar is a child widget placed in the top margin, outside the layout.
- **The border is a child widget, not the window's painting.** It covers the whole window, paints only the outer 2px, is transparent to the mouse, and is kept at the bottom of the stacking order, so the app's widgets cover it everywhere but the margin.
- **The resize zones are an event filter on the window's `QWindow`.** Every mouse event for a top-level window reaches its `QWindow` before Qt hands it to the child widget under the pointer, so a filter there sees an edge even where the app's tree view or scroll bar runs up to it — a filter on the frame's own widgets would see nothing there. In the zone it sets the resize cursor and swallows the event, so the child under it sees neither the moves nor the press and release; outside it, events pass through untouched. It is installed on the first `Show`, because a widget has no `QWindow` until then.

What the alternatives cost:

- **A wrapper widget around the app's content** takes the window's identity away from the app's code: `close()`, `setWindowTitle()`, the window state and activation all belong to the top-level widget, and would have to be forwarded. For a `QDialog` it cannot work at all — `exec()`, `accept()` and `reject()` need the dialog to *be* the window.
- **A margin around a child `QMainWindow`** is the same thing: an embedded `QMainWindow` stops being a window.
- **A stylesheet border on the content area** cascades into every child and severs palette inheritance — the reason §9 styles scroll bars one at a time — and does nothing for the title bar or for resizing.

### Things that are deliberate

- **The resize zone reaches into the content.** `RESIZE_GRAB_WIDTH` (8) from the outer edge: the 2px border plus 6px of whatever is inside, since 2px alone is too thin to hit. `RESIZE_CORNER_LENGTH` (16) along each edge from a corner counts as the corner. A window fixed in one axis (`setFixedWidth()`; a `QMessageBox` fixes both) offers no zones along it.
- **The move starts after the drag distance, not on the press.** Starting it on the press hands the pointer to the compositor before a second click can arrive, which makes double-click-to-maximize unreliable; GTK waits for the same threshold. On Wayland the compositor still accepts the move, because the button is held from the press it answers.
- **The button glyphs are painted, not icons.** Yaru ships only a close icon. Adwaita ships all four, but only as dark symbolic SVGs, which need Qt's SVG plugin to load at all (the `libqt6svg6` trap) and would then have to be recolored for this bar, for the inactive state and for the close button's hover. Each glyph is one to four 1px strokes in the color the state calls for — sharp at any scale factor, with no files.
- **Nothing in the frame holds a reference to its window.** The frame finds the window as its parent, and the buttons call the title bar's own methods rather than being connected to `window.close` and friends. A reference back would put the window in a reference cycle, so it would be freed whenever Python's cycle collector next ran instead of when its last reference went — measured, in the middle of painting the title bar, which crashed. `test_the_frame_does_not_keep_its_window_alive` is the guard.
- **The window's contents margins belong to the frame.** A host that sets them on the window itself is overwritten on the next resize. Margins on the window's *layout* are untouched and still apply inside the frame.
- **No drop shadow.** GNOME draws none round an app-drawn frame, and faking one needs a translucent margin round the window. Qt has no public API to tell a Wayland compositor that margin is not part of the window, so maximizing and tiling would leave a visible gap. The border does the job.

### What is lost against the system title bar

GNOME's window menu on a right-click of the title bar (Always on Top, Move to Workspace, …): opening it from an app needs Qt's private Wayland API. **Alt+Space** still opens it for the focused window, framed or not. An app cannot set always-on-top itself on Wayland — `Qt.WindowType.WindowStaysOnTopHint` works under X11, but the Wayland protocol has no request for it, so the user's choice in that menu is the only way.

File dialogs that Qt hands to the desktop (the GTK or portal file chooser) belong to another process and keep the system's title bar. That is expected, and not worth trading the native chooser for Qt's own.

### Testing it

What a test can reach is checked in `tests/test_frame.py`: `resize_edges()` (pure geometry) and `edge_cursor()`; where the frame puts the app's layout in each window state; which buttons there are and what they do; the painted colors, active and inactive; and that the `QWindow` filter swallows events in the zone and passes them through elsewhere. `startSystemMove()`/`startSystemResize()` are only checked for being called with the right edges — under `QT_QPA_PLATFORM=offscreen` nothing moves a window — so dragging, resizing and snapping have to be tried by hand on a real desktop.
