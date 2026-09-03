# windowchrome

This project is a dependency that's required by Sonar, Start Menu, Postit, and Lingo 
which are the four PyQt6 apps available under the 'clay-ferguson' github repositories.
To use any of those four applications you'll need to have this project in a sibling 
folder next to those folders 

This package does two unrelated things for a PyQt6 application on Linux:

1. **A colored title bar** (§1–§6), so a window reads as yours rather than as
   a gray box. Wayland only, in effect, and order-sensitive to set up.
2. **A markdown viewer** (§5), so an app can show its own documentation —
   whatever is in its `docs/` folder — inside itself, with working links and
   images. No setup, no platform requirement, and no relationship to the title
   bar beyond where it reads two colors from.

Written for an AI agent integrating it into an existing app. For the title bar,
read §4 (the checklist) and §6 (the gotchas) before changing anything, and §7
to check that what you changed actually paints. For the viewer, §5 is
self-contained.

---

## 1. What it does, and what it cannot

**Does:** paints the window's title bar — and, with it, the thin frame the
decoration draws down the sides and along the bottom — in a color of your
choosing, so a window reads as yours rather than as a gray box.

**Cannot:** change the height of the title bar, or the thickness of that frame.
Do not spend a session looking for the knob — there isn't one. On Wayland the
title bar is drawn by a Qt decoration plugin, and
`QWaylandBradientDecoration::margins()` disassembles to:

```
cmp    $0x2,%esi            ; MarginsType == ShadowsOnly?
movabs $0x1e00000003,%r8    ; packed: left=3, top=0x1e=30
cmove  %rax,%r8             ; ShadowsOnly -> all zeros
lea    (%rax,%rax,2),%eax   ; right  = 3
lea    (%rdx,%rdx,2),%rdx   ; bottom = 3
```

`QMargins{left: 3, top: 30, right: 3, bottom: 3}` — compiled-in constants with
no font, palette or environment input. Measured heights confirm it:

| plugin | title bar height | at 10pt | at 16pt |
| --- | --- | --- | --- |
| `adwaita` | 49px (incl. 11px shadow) | 49 | 49 |
| `bradient` | 30px | 30 | 30 |

3px on the sides and bottom is what you get, and it is the right amount.

**This library used to paint a thicker border of its own, just inside the
window, to work around that. It was removed deliberately — do not add it
back.** It was `bordered_body()`, and it cost every consumer a wrapper widget
per window plus two ordering rules (it overwrote the window's `objectName` and
its stylesheet); it made one app restructure its status display around it; and
on Wayland the extra band rendered at the wrong thickness while the window was
unfocused. The thin frame the decoration draws is what the design wants.

**The markdown viewer does not** render HTML, apply CSS, restyle what Qt
rendered (no theme-aware link color, no code-block background — see §5 for why
that is a decision), fetch anything over the network, offer a Forward button or
a find-in-page. It renders local markdown files, and it is deliberately not a
browser.

## 2. Requirements and platform split

- PyQt6 (≥ 6.6). No other dependency.
- **Wayland only, in effect.** The title bar is colorable because Qt draws the
  decoration inside the application process, which happens because GNOME
  implements no server-side decorations for Wayland clients. Under X11 or any
  other platform the window manager draws the bar out of process and nothing
  here can reach it: `install()` returns without doing anything, and the app
  looks exactly as it would have without this library.

## 3. Installation

`windowchrome` is **not published to PyPI**. Clone it from GitHub and consume
it from a **sibling directory** of the project using it — the sibling
relationship is what makes the `../windowchrome` path below resolve, so the
directory has to be named this and has to sit beside the consumer:

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

`editable = true` is what makes side-by-side development work: the clone is
used in place, so there is nothing to build and an edit here is picked up by
every consumer on its next run, with no reinstall. If the sibling checkout is
missing, `uv run` fails with an unresolved path dependency rather than with
anything subtle.

A consumer that is itself not an installable package keeps its own
`[tool.uv] package = false`; that governs the consumer and does not conflict
with the source above.

## 4. Integration checklist

### 1. `configure()` — before `QApplication`

```python
import windowchrome
from windowchrome import ChromeTheme

APP_THEME = ChromeTheme(title_bg="#1369da")

windowchrome.configure(APP_THEME)   # <- before the next line, always
app = QApplication(sys.argv)
```

**Why the ordering matters:** `configure()` sets `QT_WAYLAND_DECORATION`, and
the Wayland platform plugin reads that variable *inside the `QApplication`
constructor* and never again. Called afterwards it does nothing at all, and
the symptom is a gray title bar with no error anywhere.

It uses `setdefault`, so an explicit `QT_WAYLAND_DECORATION` already in the
environment still wins.

### 2. `install()` — after `QApplication`, and after your own palette work

```python
app = QApplication(sys.argv)
tune_palette(app)            # whatever the app does to its own palette
windowchrome.install(app)    # <- after that, not before
```

**Why:** `install()` captures the body's surface and text colors at the moment
it runs, then overwrites those palette roles with the title bar's. A palette
changed afterwards is a palette it never saw, and `body_window_color()` will
hand back a stale color.

It also warns (a `RuntimeWarning`) if `QT_WAYLAND_DECORATION` does not match
the theme's `decoration` — i.e. if step 1 was skipped or ran too late.

### 3. `body_window_color()` / `body_text_color()` — replace every palette read of `Window` and `WindowText`

Anywhere the app reads `QApplication.palette()` for `Window` or `WindowText` to
derive a body color, use the library's accessor instead:

```python
- window = QApplication.palette().color(QPalette.ColorRole.Window)
+ window = windowchrome.body_window_color()

- text = QApplication.palette().color(QPalette.ColorRole.WindowText)
+ text = windowchrome.body_text_color()
```

Both matter, and `WindowText` is the easier one to miss: a muted or
alpha-blended body text color derived from it comes out as the title bar's
foreground — white, typically — and vanishes against the body. `Base`,
`Highlight` and every other role are untouched and can still be read from the
palette directly. See gotcha 3.

Both accessors return a **copy**, so mutating what they hand back (`.setAlpha()`,
say) is safe. It was not always: they used to return the captured color itself,
and one app's `muted = body_text_color(); muted.setAlpha(180)` rewrote the color
the library gives every widget, washing out the whole application's text.

That is the whole integration: three calls, no per-window work, and nothing
about a window's own layout or stylesheet changes.

## 5. The markdown viewer

Independent of everything above: no `configure()`, no `install()`, no ordering,
and it works off Wayland. Two names do the whole job.

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

`show_markdown()` returns the dialog. `MarkdownView` is the widget on its own,
for markdown shown somewhere that is not a dialog — which is why the rendering
does not live inside `MarkdownDialog`.

`title` names the document the window is opened on. Anything navigated to from
there is named by its own first heading instead — a window that can follow a
link cannot keep the title it opened with, or it ends up headed "Query Syntax"
while showing the user guide.

### What Qt gives you, and what it does not

Qt renders markdown itself: `QTextBrowser.setMarkdown()` and
`setSource(url, MarkdownResource)` handle headings, tables, fenced code,
blockquotes, task lists, links and images. **No markdown package is a
dependency and none should become one.** Measured on a real 632-line document:
21268 characters, 30 headings, 12 tables, 27 fenced code blocks.

Qt's own history is enough, too. `setSource` → navigate → `backward()` returned
to the first document **and restored the scroll bar to the exact value it was
left at** (2897). So there is no history stack in this library and no scroll
bookkeeping: `backward()`, `isBackwardAvailable()` and the
`backwardAvailable(bool)` signal are the whole of it, and the last drives the
Back button's `setEnabled` directly.

What Qt does not do is give headings anchor names, so a `[Contents](#contents)`
link has nothing to scroll to, and it does not fit an image to the view. That
is the entire gap, and both are closed without changing the document.

### The rule everything else follows from: never modify the document

**This view renders what Qt renders.** It does not restyle it. There is no
theme-aware link color and no code-block background, and that is a decision
rather than an omission.

An earlier version had both, plus injected heading anchors, and the cost was
out of all proportion. Each was a pass over the rendered document merging a
format per fragment or per block — several hundred changes. Applied to a
document Qt is laying out *incrementally*, which is what happens whenever the
widget is already on screen when the content arrives, the layout stops part way
through: every block past that point keeps a height of **zero**. On screen that
is a run of paragraphs rendering as a band of blank space — text present,
selectable and copyable, but invisible and occupying almost no height.
Measured on the 632-line guide: 73 of its 302 paragraphs never laid out, and
the document reported itself 5338px tall instead of 7480.

Batching the changes into one `beginEditBlock()`/`endEditBlock()` did fix it.
The better answer was to stop making them:

- **Fragment links do not need anchors in the document.** `scroll_to_heading()`
  reads the headings, matches the slug, asks the layout where that block sits,
  and sets the scroll bar. Nothing is written. It works from `sourceChanged`
  too, before Qt has laid out the rest, because asking for a block's rectangle
  lays the document out as far as that block. It also deletes a failure mode
  outright: injected anchors had to be re-applied after every `backward()`,
  since that re-renders; found headings never need re-applying.
- **The link color is Qt's.** For the record, it cannot be changed *except* by
  modifying the document: the importer sets an explicit `ForegroundBrush` of
  `#0000ff` on every link fragment, and `QPalette.Link` is ignored — verified
  by pixel-sampling a render with the role set to red and to green, which
  painted identical blue. A host that truly needs a different link color on a
  dark background is asking for the pass that broke the layout; weigh it
  against that.
- **Code blocks are monospace, with no background band.** Cosmetic, and not
  worth touching the document for.

`MarkdownView` therefore implements exactly two things, and both are places Qt
asks a subclass to fill in rather than places it has to be reached into:

**1. `loadResource()` — image fitting.** Qt does not read image files itself:
it calls `loadResource` during layout, **before the first paint**, and lays out
whatever comes back at the size it comes back. So returning an already-scaled
`QImage` is the whole of fitting one — no walking the document afterwards
rewriting `QTextImageFormat` widths, no second layout pass, no flash of an
oversized image. Measured with a 1153×935 screenshot in a 684px viewport:
without it, horizontal scroll bar 477 and a 1161px document; with it, scroll
bar **0** and a 682px document, on the first render.

Two details that are not obvious. The base implementation returns the file's
raw bytes as a **`QByteArray`**, not an image, so decoding them is not
optional. And scaling is **down only** — a small inline icon is already the
size it wants to be.

The dialog pins its `minimumWidth` to the width it fitted images to. That is
what makes "one render" true for the life of the window: measured, dragging
narrower than the fitted width brings the overflow back (a 420px window put the
scroll bar at 278), and the only cure would be dropping the image cache,
re-rendering, and restoring the scroll position. Pinning the minimum means that
path does not exist. Widening is free — an image stays its size rather than
upscaling, which is right for a screenshot.

**2. Link handling.** `setOpenLinks(False)` and an `anchorClicked` handler,
because Qt's own is unsafe here:

- **Nothing reaches `setSource` that has not been stat'd.** `setSource` does
  not fail on a URL it cannot load: measured, an `https://` URL and a missing
  local file each left the document at **1 character** and still pushed a
  history entry, and `setOpenExternalLinks(True)` did not prevent it — that
  flag is only consulted on the click path. A click on a target that does not
  exist does nothing, which is a better outcome than a blank window.
- **An in-page link scrolls; it never calls `setSource("#x")`.** With a source
  already set, `#x` resolves *against it* and reloads: measured, 21268 → 23149
  characters and the scroll bar did not move.

Slugs are GitHub's rule over the *rendered* block text, `-1`/`-2` for repeats.
Rendered, not source: the importer has already eaten the backticks, so
`` ## `search.included` `` arrives as `search.included` and slugs to
`searchincluded`, which is what GitHub produces for the same heading — so a
link written against the file on GitHub resolves against the file in the
widget. `heading_slugs()` is exported for exactly one reason: anything that
*checks* a document's links must number repeats identically, and a checker with
its own copy of the rule is one that will eventually disagree with the view.

`test_the_document_is_never_modified` asserts `document().isModified()` is
false after loading and navigating. That is the guard on all of the above: any
styling pass that creeps back in has to modify the document, and would fail it.

### Buttons, and why there is a factory

The dialog owns no look beyond its layout. The four applications using this
library each build a button differently — a colored free function, a stylesheet
constant on a `QDialogButtonBox`, a method on the main window that wires the
slot too, and a `QToolButton` — so there is no convention to standardise on
here. `button_factory` is the narrowest seam all of them can satisfy, and it is
typed `Callable[[str], QAbstractButton]` because of that last one.

Without a factory the buttons are bare `QPushButton`s wearing the desktop
theme, deliberately: an integration that forgets is one that looks wrong
immediately rather than looking almost right forever.

`.view` and `.button_row` are public for the styling a factory cannot reach —
a host that widens its scroll bars everywhere calls `apply_scrollbars(dlg.view)`
on what `show_markdown()` hands back.

### The registry, and the two ways a dialog dies

Windows are modeless and kept in a module-level dict keyed by the resolved
path, so asking for a document twice raises the window already showing it.
Eviction is the subtle part, and it is measured:

- **A dismissed dialog must be evicted synchronously.** `close()`, `reject()`
  and Escape all emit `finished` immediately, but deletion is a `deleteLater`
  that lands on a later turn. Evicting only on `destroyed` leaves a dialog that
  is on its way out still registered — so the next open "raises" it and hands
  back a window that vanishes a moment later. Hence `finished`, with
  `destroyed` kept as the backstop for a dialog torn down without being closed.
- **Eviction compares identity, and never calls a method on the dialog.**
  `destroyed` arrives a turn late: close A, open B for the same path, and A's
  notification lands with B already registered. Without `_WINDOWS.get(key) is
  dialog`, B is evicted and a third open stacks a duplicate. The check is a
  Python wrapper comparison, which is also the only kind that is safe from a
  `destroyed` handler — by then the C++ object is gone and touching it raises.
- `close_markdown_windows()` iterates a **copy**, because each close mutates
  the dict.

**A parented modeless dialog does not hold the application open.** It has a
transient parent, so it is not a "primary" window and `quitOnLastWindowClosed`
still fires — measured, the app quit with a help window visible. But that
window *is* still on screen for as long as that takes, so a host should still
call `close_markdown_windows()` from its main window's `closeEvent`. An
*unparented* window is a different story and would keep the process alive.

## 6. The gotchas

Each of these was measured. They are what stop a future integrator from
"fixing" the design.

### 1. Giving a widget a stylesheet severs its palette inheritance

`QStyleSheetStyle` resolves a palette for a styled widget out of the
*application* palette and assigns it, so the widget stops inheriting from its
parent — and everything beneath it inherits the severed one. A window is
severed too, simply by being a window: a dialog or a popup resolves against
the application palette however it is parented.

**Measured:** setting the body palette on the main window alone left **22
widgets** wearing the title bar color. With the event filter `install()`
puts on the application: **0**.

The filter acts on `QEvent.Polish`, `QEvent.StyleChange` **and**
`QEvent.PaletteChange`. Polish alone is one pass per widget and misses the
subtree beneath a later-styled ancestor (a splitter styled after both its panes
have been polished); StyleChange is what that repolish arrives as.

`PaletteChange` is there because neither of the other two is late enough.
**An application event filter runs before the receiver handles the event**, so
on Polish the order is: the filter corrects the palette, and *then*
`QWidget::event()` reaches `QStyleSheetStyle::polish()`, which re-derives one
from the application palette and assigns it — overwriting the correction made
moments earlier. `PaletteChange` is the event that assignment raises, which
makes it the one trigger guaranteed to arrive after any palette is set, by
anyone.

The symptom that found it: **a `QComboBox` dropdown painted in the title bar's
color.** Measured in a styled dialog — the popup view's `Window` role read
correctly at every Polish and StyleChange the filter saw, and was the title
bar's color once everything settled. A combo popup is where this surfaces
because `QStyleSheetStyle` treats `QComboBox QAbstractItemView` as a styled
sub-control and always assigns it a palette, whether or not the app wrote a
rule for one.

It cannot loop: `_apply_body_palette()` returns without writing when the colors
are already right, so the filter's own `setPalette` re-enters it and stops.
Measured re-entry depth: 3, bounded. That early return is load-bearing.

**The symptom to recognise:** a widget wearing the title bar color *only while
the window has focus*. Only the `Active` group is repurposed, so anything
leaking reverts to the theme's gray the moment the window is defocused.

### 2. Some widgets paint from the application palette, not their own

The event filter above can only reach widgets that resolve a color *from their
own palette*. An **unstyled** `QComboBox` popup does not: it paints its
background from `QApplication.palette()` at paint time, so the drop-down opens
in the title bar's color no matter what the filter did.

Measured, and worth knowing how it was pinned down: with every widget in the
popup reading `Window = <body color>`, the popup still rendered the title bar's
blue — and changing *only* the application palette, with the filter removed so
no widget palette moved, took the popup with it. That is what proves the paint
follows the application palette rather than the widget's.

A stylesheet breaks the tie. Any stylesheet on the combo or its view switches
it to `QStyleSheetStyle`, which resolves from the widget palette instead —
which is why this appears in one app and not another: **an app that merely pads
its combo has already fixed this by accident.** `install()`'s filter writes the
rule for popups that have no stylesheet of their own, and leaves a view the
host has already styled alone.

If you meet the same symptom on some other widget, this is the shape of it:
check whether changing only the application palette moves it.

### 3. Never derive a body color from `QApplication.palette()`

The `Window` and `WindowText` roles carry the *title bar's* colors once
`install()` has run, so a derived color comes out tinted — and, where it
lightens or darkens what it read, wrong twice over. One host app's splitter
handle did exactly this: it read the title bar blue and lightened it, painting
the handle a *brighter* blue than the bar. Another computed its muted help text
from `WindowText` and would have drawn it in the title bar's white.
`body_window_color()` and `body_text_color()` are the fix and the rule.

### 4. The decoration plugin choice is silent when wrong

Qt ships exactly two decoration plugins and defaults to `adwaita`:

| `QT_WAYLAND_DECORATION` | plugin loaded (from `/proc/self/maps`) |
| --- | --- |
| *(unset)* | `libadwaita.so` |
| `bradient` | `libbradient.so` |
| an unknown name | `libadwaita.so` — silent fallback, no error |

`libadwaita.so` links **no `QPalette` symbol at all** (`nm -DC` confirms): its
grays are compiled in and unreachable from application code.
`libbradient.so` links `QPalette::brush()`, and disassembling
`QWaylandBradientDecoration::paint()` shows **exactly three** call sites —
`(Active, Window)`, `(Active, WindowText)`, `(Disabled, WindowText)` — re-read
on every repaint rather than cached at construction. Those three roles are
what this library repurposes, and why the body palette has to be handed back.

## 7. How to verify an integration

None of this is unit-testable — it is pixels and a plugin choice — so check it
directly.

**Which decoration actually loaded:**

```python
import re
print(re.findall(r'/\S*(?:adwaita|bradient)\S*\.so',
                 open('/proc/self/maps').read()))
```

Expect `libbradient.so`. `libadwaita.so` means `configure()` ran too late, or
the decoration name is wrong.

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

**The colors reached the palette.** There is no way to sample the title bar's
own pixels from inside the process — the decoration is drawn outside the
widget tree, so `grab()` never sees it. What can be checked is the palette the
decoration reads, and that the body did not go with it:

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

The first line must be the theme's `title_bg`/`title_fg`; the second must be
the colors the app had before `install()` ran. (Both come back identical off
Wayland, where `install()` is a no-op — run this under a real session.)

**By eye:** run the app. The title bar and the thin frame down the sides and
along the bottom are the theme's color; nothing *inside* the window is.

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
