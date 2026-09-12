# windowchrome

This project is a dependency that's required by Sonar, Start Menu, Postit, and Lingo which are the four PyQt6 apps available under the 'clay-ferguson' github repositories. To use any of those four applications you'll need to have this project in a sibling folder next to those folders

This package does five unrelated things for a PyQt6 application on Linux:

1. **A colored title bar** (§1–§6), in a font of your choosing, so a window reads as yours rather than as a gray box. Wayland only, in effect, and order-sensitive to set up.
2. **A markdown viewer** (§5), so an app can show its own documentation — whatever is in its `docs/` folder — inside itself, with working links and images. No setup, no platform requirement, and no relationship to the title bar beyond where it reads two colors from.
3. **Wide scroll bars** (§9), about twice the thickness the desktop draws, so they are easier to grab with the mouse. Per scroll area, opt-in, and self-contained.
4. **Radio buttons** (§10) with an enlarged, visibly outlined indicator, in place of the small near-black one the desktop draws. Per button, opt-in, and self-contained in the same way.
5. **A toggle switch** (§11) — a track with a sliding knob, to put where a check box would have gone. A widget you construct rather than a style you apply, and self-contained in the same way.
6. **Check boxes** (§12) with an enlarged indicator, keeping the tick Qt draws. A style rather than a stylesheet, for the reason §12 gives. Per box, opt-in, and self-contained in the same way.

Written for an AI agent integrating it into an existing app. For the title bar, read §4 (the checklist) and §6 (the gotchas) before changing anything, and §7 to check that what you changed actually paints. For the viewer, §5 is self-contained, and so are §9 for the scroll bars, §10 for the radio buttons, §11 for the toggle switch and §12 for the check boxes.

The numbering is historical: §9 was added after §7 and §8 were written, and is not renumbered into place because the four consuming apps cite these section numbers from their own `AGENTS.md`.

---

## 1. What it does, and what it cannot

**Does:** paints the window's title bar — and, with it, the thin frame the decoration draws down the sides and along the bottom — in a color of your choosing, so a window reads as yours rather than as a gray box. Sets the *weight* and *stretch* the title is drawn at, and keeps the title one color whether the window is focused or not.

**Cannot:** change the height of the title bar, the thickness of that frame, or the title's font *size*. Do not spend a session looking for the knob — there isn't one. On Wayland the title bar is drawn by a Qt decoration plugin, and `QWaylandBradientDecoration::margins()` disassembles to:

```
cmp    $0x2,%esi            ; MarginsType == ShadowsOnly?
movabs $0x1e00000003,%r8    ; packed: left=3, top=0x1e=30
cmove  %rax,%r8             ; ShadowsOnly -> all zeros
lea    (%rax,%rax,2),%eax   ; right  = 3
lea    (%rdx,%rdx,2),%rdx   ; bottom = 3
```

`QMargins{left: 3, top: 30, right: 3, bottom: 3}` — compiled-in constants with no font, palette or environment input. Measured heights confirm it:

| plugin | title bar height | at 10pt | at 16pt |
| --- | --- | --- | --- |
| `adwaita` | 49px (incl. 11px shadow) | 49 | 49 |
| `bradient` | 30px | 30 | 30 |

3px on the sides and bottom is what you get, and it is the right amount.

**This library used to paint a thicker border of its own, just inside the window, to work around that. It was removed deliberately — do not add it back.** It was `bordered_body()`, and it cost every consumer a wrapper widget per window plus two ordering rules (it overwrote the window's `objectName` and its stylesheet); it made one app restructure its status display around it; and on Wayland the extra band rendered at the wrong thickness while the window was unfocused. The thin frame the decoration draws is what the design wants.

**Nor is the title's point size a knob**, for the same kind of reason one level down. `QWaylandBradientDecoration::paint()` takes the painter's font and overwrites its size:

```
call   4980 <QPainter::font() const@plt>    ; the painter's font...
call   49c0 <QFont::QFont(QFont const&)>    ; ...copied...
mov    $0xe,%esi                            ; ...and 14px, compiled in
call   47b0 <QFont::setPixelSize(int)@plt>
```

So 14 pixels it is, whatever point size the application font carries. Weight, stretch, family and italic all survive, because the plugin overwrites none of them — which is what `title_font_weight` and `title_font_stretch` reach. `title_font_stretch` is the only lever pointing at "bigger".

**And the title's color does not change when the window loses focus** — not by default. That is `title_fg_inactive`, which defaults to the same white as `title_fg` rather than to a dimmed version of it. `bradient` paints the title from the palette's `Disabled` group whenever the window is not the active one, and on Wayland that includes the whole of an interactive move: grab the bar, and keyboard focus goes with the drag. A title that dims the instant the window is picked up reads as the window breaking rather than as a focus cue. Set `title_fg_inactive` to something dimmer to get the conventional look back.

**The markdown viewer does not** render HTML, apply CSS, restyle what Qt rendered (no theme-aware link color, no code-block background — see §5 for why that is a decision), fetch anything over the network, offer a Forward button or a find-in-page. It renders local markdown files, and it is deliberately not a browser.

## 2. Requirements and platform split

- PyQt6 (≥ 6.6). No other dependency.
- **Wayland only, in effect.** The title bar is colorable because Qt draws the decoration inside the application process, which happens because GNOME implements no server-side decorations for Wayland clients. Under X11 or any other platform the window manager draws the bar out of process and nothing here can reach it: `install()` returns without doing anything, and the app looks exactly as it would have without this library.

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

## 4. Integration checklist

### 1. `configure()` — before `QApplication`

```python
import windowchrome
from windowchrome import ChromeTheme

APP_THEME = ChromeTheme(title_bg="#1369da")

windowchrome.configure(APP_THEME)   # <- before the next line, always
app = QApplication(sys.argv)
```

**Why the ordering matters:** `configure()` sets `QT_WAYLAND_DECORATION`, and the Wayland platform plugin reads that variable *inside the `QApplication` constructor* and never again. Called afterwards it does nothing at all, and the symptom is a gray title bar with no error anywhere.

It uses `setdefault`, so an explicit `QT_WAYLAND_DECORATION` already in the environment still wins.

### 2. `install()` — after `QApplication`, and after your own palette and font work

```python
app = QApplication(sys.argv)
tune_palette(app)            # whatever the app does to its own palette
app.setFont(app_font)        # ... and to its own default font
windowchrome.install(app)    # <- after both, not before
```

**Why:** `install()` captures the body's surface color, text color and font at the moment it runs, then overwrites those palette roles — and the application font — with the title bar's. A palette or font changed afterwards is one it never saw, and `body_window_color()` will hand back a stale color.

**An `app.setFont()` *after* `install()` is worse than merely unseen.** `QApplication::setFont(font)` with no class name clears the class-font table, which is where `install()` put the body font for every widget to inherit — so the body font stops being handed back and the whole application comes out in the title's weight. Set the app font first; `install()` will pick it up.

It also warns (a `RuntimeWarning`) if `QT_WAYLAND_DECORATION` does not match the theme's `decoration` — i.e. if step 1 was skipped or ran too late.

### 3. `body_window_color()` / `body_text_color()` — replace every palette read of `Window` and `WindowText`

Anywhere the app reads `QApplication.palette()` for `Window` or `WindowText` to derive a body color, use the library's accessor instead:

```python
- window = QApplication.palette().color(QPalette.ColorRole.Window)
+ window = windowchrome.body_window_color()

- text = QApplication.palette().color(QPalette.ColorRole.WindowText)
+ text = windowchrome.body_text_color()
```

Both matter, and `WindowText` is the easier one to miss: a muted or alpha-blended body text color derived from it comes out as the title bar's foreground — white, typically — and vanishes against the body. `Base`, `Highlight` and every other role are untouched and can still be read from the palette directly. See gotcha 3.

Both accessors return a **copy**, so mutating what they hand back (`.setAlpha()`, say) is safe. It was not always: they used to return the captured color itself, and one app's `muted = body_text_color(); muted.setAlpha(180)` rewrote the color the library gives every widget, washing out the whole application's text.

### 4. `body_font()` — for a `QPainter` on a pixmap, and nothing else

Widgets need no change: the body font is handed back to them as a class font, so a widget's own `setFont()` and a stylesheet's `font-size` both keep working exactly as before. What does need changing is code that reads the *application* font directly, and in practice that means a painter over a pixmap or an image:

```python
- font = painter.font()        # a QPainter on a pixmap starts with the app font
+ font = windowchrome.body_font()
  font.setPointSize(...)
  painter.setFont(font)
```

That default *is* the title font now — it is the very path the decoration takes to draw the title — so a glyph rendered into an icon comes out bold unless it starts here. Like the two color accessors, this returns a **copy**, so resizing what it hands back is safe. See gotcha 5 for the one other place the title font is briefly visible.

That is the whole integration: three calls plus whatever `body_*` reads the app already had, no per-window work, and nothing about a window's own layout or stylesheet changes.

## 5. The markdown viewer

Independent of everything above: no `configure()`, no `install()`, no ordering, and it works off Wayland. Two names do the whole job.

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

## 6. The gotchas

Each of these was measured. They are what stop a future integrator from "fixing" the design.

### 1. Giving a widget a stylesheet severs its palette inheritance

`QStyleSheetStyle` resolves a palette for a styled widget out of the *application* palette and assigns it, so the widget stops inheriting from its parent — and everything beneath it inherits the severed one. A window is severed too, simply by being a window: a dialog or a popup resolves against the application palette however it is parented.

**Measured:** setting the body palette on the main window alone left **22 widgets** wearing the title bar color. With the event filter `install()` puts on the application: **0**.

The filter acts on `QEvent.Polish`, `QEvent.StyleChange` **and** `QEvent.PaletteChange`. Polish alone is one pass per widget and misses the subtree beneath a later-styled ancestor (a splitter styled after both its panes have been polished); StyleChange is what that repolish arrives as.

`PaletteChange` is there because neither of the other two is late enough. **An application event filter runs before the receiver handles the event**, so on Polish the order is: the filter corrects the palette, and *then* `QWidget::event()` reaches `QStyleSheetStyle::polish()`, which re-derives one from the application palette and assigns it — overwriting the correction made moments earlier. `PaletteChange` is the event that assignment raises, which makes it the one trigger guaranteed to arrive after any palette is set, by anyone.

The symptom that found it: **a `QComboBox` dropdown painted in the title bar's color.** Measured in a styled dialog — the popup view's `Window` role read correctly at every Polish and StyleChange the filter saw, and was the title bar's color once everything settled. A combo popup is where this surfaces because `QStyleSheetStyle` treats `QComboBox QAbstractItemView` as a styled sub-control and always assigns it a palette, whether or not the app wrote a rule for one.

It cannot loop: `_apply_body_palette()` returns without writing when the colors are already right, so the filter's own `setPalette` re-enters it and stops. Measured re-entry depth: 3, bounded. That early return is load-bearing.

**The symptom to recognise:** a widget wearing the title bar color *only while the window has focus*. Only the `Active` group is repurposed, so anything leaking reverts to the theme's gray the moment the window is defocused.

### 2. Some widgets paint from the application palette, not their own

The event filter above can only reach widgets that resolve a color *from their own palette*. An **unstyled** `QComboBox` popup does not: it paints its background from `QApplication.palette()` at paint time, so the drop-down opens in the title bar's color no matter what the filter did.

Measured, and worth knowing how it was pinned down: with every widget in the popup reading `Window = <body color>`, the popup still rendered the title bar's blue — and changing *only* the application palette, with the filter removed so no widget palette moved, took the popup with it. That is what proves the paint follows the application palette rather than the widget's.

A stylesheet breaks the tie. Any stylesheet on the combo or its view switches it to `QStyleSheetStyle`, which resolves from the widget palette instead — which is why this appears in one app and not another: **an app that merely pads its combo has already fixed this by accident.** `install()`'s filter writes the rule for popups that have no stylesheet of their own, and leaves a view the host has already styled alone.

If you meet the same symptom on some other widget, this is the shape of it: check whether changing only the application palette moves it.

### 3. Never derive a body color from `QApplication.palette()`

The `Window` and `WindowText` roles carry the *title bar's* colors once `install()` has run, so a derived color comes out tinted — and, where it lightens or darkens what it read, wrong twice over. One host app's splitter handle did exactly this: it read the title bar blue and lightened it, painting the handle a *brighter* blue than the bar. Another computed its muted help text from `WindowText` and would have drawn it in the title bar's white. `body_window_color()` and `body_text_color()` are the fix and the rule.

### 4. The decoration plugin choice is silent when wrong

Qt ships exactly two decoration plugins and defaults to `adwaita`:

| `QT_WAYLAND_DECORATION` | plugin loaded (from `/proc/self/maps`) |
| --- | --- |
| *(unset)* | `libadwaita.so` |
| `bradient` | `libbradient.so` |
| an unknown name | `libadwaita.so` — silent fallback, no error |

`libadwaita.so` links **no `QPalette` symbol at all** (`nm -DC` confirms): its grays are compiled in and unreachable from application code. `libbradient.so` links `QPalette::brush()`, and disassembling `QWaylandBradientDecoration::paint()` shows **exactly three** call sites — `(Active, Window)`, `(Active, WindowText)`, `(Disabled, WindowText)` — re-read on every repaint rather than cached at construction. Those three roles are what this library repurposes, and why the body palette has to be handed back.

### 5. The application font is the title bar's font

There is no font on a Qt Wayland decoration to set. `bradient` paints the title with `QPainter::font()` over the window's backing store — a non-widget paint device, so that font is `QGuiApplication::font()`, plain and unqualified. Making the title bold therefore means making the *application* font bold, exactly as coloring the bar means repurposing `Window` and `WindowText`, and the body has to be handed its own font back.

That handback is a **class font** — `app.setFont(body, "QWidget")` — not the polish-time filter the palette needs, and the difference is worth knowing: a class font is the default a widget *resolves against*, so a widget that set its own font keeps it and a stylesheet's `font-size` still merges on top, while a filter would have to overwrite a widget's font to place it and could not tell an explicit font from an inherited one. One entry covers everything, because `QApplicationPrivate::font(w)` matches a class font by `w->inherits(key)`. And unlike the palette, nothing leaks past it: `QStyleSheetStyle` resolves a font from the *parent widget* rather than from the application, which is precisely what it does not do for palettes.

Two places still see the title font, and both are the mechanism showing through rather than a bug:

- **A `QPainter` on a pixmap or image**, per step 4 of §4 — `body_font()` is the answer.
- **A top-level widget, between its constructor and its first show.** `QWidget`'s constructor seeds a *window's* font from `QApplication::font()` with no widget argument; the class font only reaches it when the font is re-resolved, at polish. It is never painted with — but a window that measures `self.font()` in its own constructor measures the title font and sizes itself a little wide. `body_font()` again. A child widget is unaffected at every point.

`tests/test_titlefont.py` pins all of it down, including the ordering rule, by calling the font half directly — which is the only part of the title bar that *is* testable off Wayland.

## 7. How to verify an integration

None of this is unit-testable — it is pixels and a plugin choice — so check it directly.

**Which decoration actually loaded:**

```python
import re
print(re.findall(r'/\S*(?:adwaita|bradient)\S*\.so',
                 open('/proc/self/maps').read()))
```

Expect `libbradient.so`. `libadwaita.so` means `configure()` ran too late, or the decoration name is wrong.

**Which plugin can read a palette at all:**

```bash
nm -DC /usr/lib/x86_64-linux-gnu/qt6/plugins/wayland-decoration-client/lib{adwaita,bradient}.so \
  | grep -c QPalette
```

**Nothing leaked the title bar color:**

```python
leaked = [w for w in app.allWidgets()
          if w.palette().color(QPalette.ColorGroup.Active,
                               QPalette.ColorRole.Window).name()
          == APP_THEME.title_bg]
assert leaked == []
```

**Nothing leaked the title bar font** (which, unlike the color, only shows up on a widget that was never shown — see gotcha 5):

```python
title_weight = QApplication.font().weight()
leaked = [w for w in app.allWidgets()
          if w.isVisible() and w.font().weight() == title_weight
          and w.font().weight() != windowchrome.body_font().weight()]
assert leaked == []
```

**The colors reached the palette.** There is no way to sample the title bar's own pixels from inside the process — the decoration is drawn outside the widget tree, so `grab()` never sees it. What can be checked is the palette the decoration reads, and that the body did not go with it:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette
import windowchrome
from yourapp.style import APP_THEME, tune_palette

windowchrome.configure(APP_THEME)
app = QApplication(sys.argv)
tune_palette(app)
windowchrome.install(app)

p = app.palette()
print("title bar reads:",
      p.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window).name(),
      p.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText).name())
print("body keeps:     ",
      windowchrome.body_window_color().name(),
      windowchrome.body_text_color().name())
```

The first line must be the theme's `title_bg`/`title_fg`; the second must be the colors the app had before `install()` ran. (Both come back identical off Wayland, where `install()` is a no-op — run this under a real session.)

**By eye:** run the app. The title bar and the thin frame down the sides and along the bottom are the theme's color; nothing *inside* the window is.

## 8. Troubleshooting

| Symptom | Cause |
| --- | --- |
| Gray title bar | `configure()` ran after `QApplication`, or `decoration` names a plugin Qt does not ship (it falls back to `adwaita` silently). Check `/proc/self/maps`. |
| Gray title bar, no warning, not Wayland | Expected. The title bar is drawn out-of-process under X11 and nothing here can reach it. Check `app.platformName()`. |
| A widget is colored like the title bar, but **only when focused** | A palette leak: `install()` was not called, or was called before the app's own palette tuning. Only the `Active` group is repurposed, which is why defocusing reverts it. |
| A whole window is colored like the title bar | The same leak, on a window. `install()` puts an application-wide event filter on for exactly this; check it ran. |
| A derived color (splitter, handle, hover) comes out tinted with the title bar | Something still reads `QApplication.palette()` for `Window`. Use `body_window_color()`. |
| Muted/derived text is white and unreadable on the body | Something reads `QApplication.palette()` for `WindowText`. Use `body_text_color()`. |
| A `QComboBox` dropdown, menu or other popup is painted like the title bar | Two different causes. A late palette assignment the filter did not catch — `PaletteChange` is a trigger for exactly this, check it is still in `_TRIGGERS`. Or a widget painting from the application palette rather than its own, which no palette fix can reach: see gotcha 2. |
| A combo dropdown is right in one app and blue in another | The one that works styles its combo, which quietly switches it to `QStyleSheetStyle`. See gotcha 2. |
| All the app's text is faintly washed out | Something mutated a color the accessors returned. They hand back copies now; if you add an accessor, copy in it too. |

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

Nothing to call before or after the `QApplication`, no platform requirement, and no relationship to the title bar. It is opt-in per scroll area rather than an application-wide stylesheet, because an application-wide one would sever palette inheritance across every widget in the app (gotcha 1) to change two.

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

### Why this reads the palette directly

This is the one place in the library that reads a color straight from `QApplication.palette()`, and gotcha 3 says not to. Gotcha 3 is about `Window` and `WindowText`, the two roles `install()` repurposes for the title bar — a body color derived from those has to come from `body_window_color()`/`body_text_color()` or it comes out tinted with the title bar. `Base` is not one of them and is never touched, so reading it here is correct, and routing it through the body accessors would be actively wrong.

---

## 10. Radio buttons

The native radio indicator is small — around 13px — and rings itself in a near-black that all but disappears against a dark dialog. `radio_style()` returns a Qt stylesheet drawing a bigger one in a color that shows, and `apply_radios()` puts it on the buttons:

```python
from windowchrome import apply_radios

apply_radios(self._file_radio, self._sh_radio,
             base=field_background, point_size=UI_POINT_SIZE)
```

Like the scroll bars (§9): nothing to call before or after the `QApplication`, no platform requirement, no relationship to the title bar, and opt-in per widget rather than an application-wide stylesheet that would sever palette inheritance everywhere (gotcha 1).

Three things about it are deliberate:

- **The whole indicator has to be described.** Styling `::indicator` at all opts the button out of native drawing, so the circle, its ring and the checked state are all this stylesheet's problem. There is no "keep the native dot, just bigger".
- **The checked state is a filled circle, not a ring with a dot in it.** A stylesheet element has one border, so a gap between the ring and an inner dot cannot be drawn without giving up the ring — and the ring is what makes the *unchecked* state visible at all. At `RADIO_INDICATOR_SIZE` (22px) a solid fill is unambiguous.
- **The ring and the fill come from the palette's `Text`.** So the indicator reads as bright as the label beside it, and follows the desktop between a light theme and a dark one instead of pinning a gray that suits one of them. This is the same direct palette read §9 makes, and for the same reason it is not the gotcha-3 mistake: `install()` repurposes `Window` and `WindowText`, and `Text`/`Base` are untouched.

`base` is the color painted inside an unchecked circle — the same argument, with the same reasoning, as the scroll bars' `base` (§9). It defaults to the palette's `Base`; a host whose dialog fields are painted some color derived from `Base` passes that instead. `point_size` sets the label's font size, and is left to the widget's own font when omitted.

---

## 11. The toggle switch

Where a setting is on or off and the app wants to *say* so — a mode you can see from across the room — `ToggleSwitch` draws the switch a phone's settings screen draws: a rounded track with a knob that slides to the far end when it is on.

```python
from windowchrome import ToggleSwitch

self.edit_toggle = ToggleSwitch(self, on_color=HIGHLIGHT_BG)
self.edit_toggle.toggled.connect(self._handle_edit_toggled)
```

Like the scroll bars (§9) and the radio buttons (§10): nothing to call before or after the `QApplication`, no platform requirement, and no relationship to the title bar.

Three things about it are worth knowing:

- **It is a painted widget, not a stylesheet.** The other two helpers are stylesheets because what was wrong with the native widget was its size and its color. Here the *shape* is wrong: a check box indicator is a square with a tick in it, and no stylesheet moves a knob from one end of a track to the other. Qt's own route would be a pair of images swapped on toggle, which pins the colors into files. A checkable `QAbstractButton` with its own `paintEvent` is a dozen lines and follows whatever colors it is handed.
- **It is still the button it inherits from.** `isChecked()`, `setChecked()`, `toggle()`, `toggled`/`clicked`, Space to flip it, and the focus and tab behavior are all `QAbstractButton`'s. Only the painting is this library's, so a host swapping a `QCheckBox` for one changes the constructor and nothing else. It has no label of its own — put a `QLabel` beside it, which is what a settings row wants anyway.
- **Its size is fixed, not laid out.** `TOGGLE_WIDTH`×`TOGGLE_HEIGHT` (40×22) by default, overridable per switch with `width=`/`height=`. A layout that stretched the track would not stretch the knob's travel with it, and the travel is what reads as a switch.

`on_color` is the track while checked — the host's accent, and the one argument worth passing; it defaults to the palette's `Highlight`. `off_color` (`#888888`) and `knob_color` (`#ffffff`) are pinned rather than taken from the palette: `Window` is the title bar's under `install()`, and `Base` is the pane the switch is sitting on, so a switch painted from either would disappear into its background. Both are overridable. All three take a `QColor` or anything `QColor` accepts, since a host's accent is usually already a `"#rrggbb"` constant.

---

## 12. Check boxes

The native check box indicator is around 13px — sized for a mouse that never misses. `apply_checkboxes()` draws it at `CHECKBOX_SCALE` (2) times that, and changes nothing else about the widget:

```python
from windowchrome import apply_checkboxes

apply_checkboxes(self.wrap_check, self.archive_check)
```

Like the scroll bars (§9), the radio buttons (§10) and the toggle switch (§11): nothing to call before or after the `QApplication`, no platform requirement, no relationship to the title bar, and opt-in per widget rather than an application-wide style.

Three things about it are deliberate:

- **It is a `QProxyStyle`, not a stylesheet, and that is not an oversight.** A stylesheet `QCheckBox::indicator { width: …; height: … }` does work: geometry is all it sets, so `QStyleSheetStyle` applies the size and still lets the native style paint the box and its tick. It works only while the rule stays geometry, though — add a `border` or a `background` and Qt takes the drawing to be yours, stops delegating, and paints only what the rule names. No CSS property draws a check mark (Qt's answer is `image: url(tick.png)`, i.e. images for every state), so the indicator renders empty and a checked box stops looking checked. Measured: `width`/`height` alone keeps the tick, `border: 2px solid #444` loses it. The proxy exists because that failure is silent and one word away — overriding the pixel metric changes the rectangle the native style is handed and never leaves the native drawing path. `radio_style()` (§10) goes the stylesheet route because a circle *is* drawable in CSS and a tick is not.
- **Only `PM_IndicatorWidth`/`PM_IndicatorHeight` are answered; every other metric is forwarded.** A style that scaled anything else would grow the widget's spacing and frames along with the box. `PM_ExclusiveIndicatorWidth` — the *radio* indicator — is among the metrics left alone, so the two helpers do not overlap. `test_every_other_metric_is_left_alone` is the guard.
- **A style is built per box and parented to it.** Not one shared instance and not `QApplication.setStyle()`: this is one widget's affordance, not a change of theme. The parenting is also load-bearing — `setStyle()` does not take ownership, so a style with no parent is collected out from under a live widget and crashes it.

One thing to know before writing a test or debugging one: **`box.style()` does not necessarily hand this style back.** As soon as any ancestor widget carries a stylesheet, Qt slips its own `QStyleSheetStyle` in front of the widget's style and `style()` returns *that*. The metric still comes through it — the indicator is drawn at the enlarged size either way — but an `isinstance` check against `LargeIndicatorStyle` passes on a bare check box and fails on the same box inside a real window. Ask the box for the metric, or for `findChildren(LargeIndicatorStyle)`, and not for `style()`'s type.

Nothing here reads the palette, unlike §9 and §10: the native drawing already follows the theme, and only the size was ever wrong. `LargeIndicatorStyle` is exported for a host that wants the style object itself — to hand to a widget `apply_checkboxes()` does not cover, say — but the applier is the interface.

Where a check box is the wrong *shape* rather than the wrong size — an on/off setting the app wants to state loudly — `ToggleSwitch` (§11) is the other answer.
