# windowchrome

This project is a dependency that's required by Sonar, Start Menu, Postit, and Lingo which are the four PyQt6 apps available under the 'clay-ferguson' github repositories. To use any of those four applications you'll need to have this project in a sibling folder next to those folders

This package does five unrelated things for a PyQt6 application on Linux:

1. **A markdown viewer** (§5), so an app can show its own documentation — whatever is in its `docs/` folder — inside itself, with working links and images.
2. **Wide scroll bars** (§9), about twice the thickness the desktop draws, so they are easier to grab with the mouse. Per scroll area, opt-in, and self-contained.
3. **Radio buttons** (§10) with an enlarged, visibly outlined indicator, in place of the small near-black one the desktop draws. Per button, opt-in, and self-contained in the same way.
4. **A toggle switch** (§11) — a track with a sliding knob, to put where a check box would have gone. A widget you construct rather than a style you apply, and self-contained in the same way.
5. **Check boxes** (§12) with an enlarged indicator, keeping the tick Qt draws. A style rather than a stylesheet, for the reason §12 gives. Per box, opt-in, and self-contained in the same way.

None of them needs a setup call, an ordering rule around `QApplication`, or any particular platform. Written for an AI agent integrating it into an existing app: §3 covers installation, and each of §5, §9, §10, §11 and §12 is self-contained.

**There is no window chrome here, deliberately.** This library used to color the title bar and window frame, by choosing Qt's `bradient` Wayland decoration plugin and repurposing application palette roles and the application font for it. That was removed as too fragile — it rested on undocumented plugin internals and leaked into every consuming app. Do not reintroduce it.

The numbering is historical: the sections that described the title bar (§1, §4, §6, §7) are gone, and the rest keep their numbers because the consuming apps cite them from their own `AGENTS.md`.

---

## 2. Requirements

- PyQt6 (≥ 6.6). No other dependency.
- No platform requirement: nothing here depends on Wayland, X11 or the window manager.

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
