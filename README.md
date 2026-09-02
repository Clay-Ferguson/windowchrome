# windowchrome

A colored title bar and a colored window border for PyQt6 applications on
Linux. Written for an AI agent integrating it into an existing app: read §4
(the checklist) and §5 (the gotchas) before changing anything, and §6 to check
that what you changed actually paints.

---

## 1. What it does, and what it cannot

**Does:** paints the window's title bar in a color of your choosing, and paints
a border of your chosen width just inside the window, so a window reads as one
framed object rather than as a gray box with a colored strip on top.

**Cannot:** change the height of the title bar, or the thickness of the
decoration's own border. Do not spend a session looking for the knob — there
isn't one. On Wayland the title bar is drawn by a Qt decoration plugin, and
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

**That is why this library paints its own border inside the window.** The 3px
the decoration draws cannot be widened, so `bordered_body()` paints
`border_width` more of the same color immediately inside it, flush against it,
and the two read as one thicker frame.

## 2. Requirements and platform split

- PyQt6 (≥ 6.6). No other dependency.
- **The border works everywhere.** It is ordinary layout and an ordinary
  stylesheet.
- **The title bar color is Wayland-only.** It depends on Qt drawing the
  decoration inside the application process, which happens because GNOME
  implements no server-side decorations for Wayland clients. Under X11 or any
  other platform the window manager draws the bar out of process and nothing
  here can reach it: `install()` returns without doing anything, and
  `bordered_body()` still paints its border.

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

APP_THEME = ChromeTheme(title_bg="#1369da", border_width=4)

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

### 3. `bordered_body()` — in every top-level window

Every `QMainWindow`, every `QDialog`. **Build into the widget it returns, not
into the one you passed it.**

```python
# a dialog
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout(windowchrome.bordered_body(self))
        ...

# a main window: the menu bar above carries its own inset, so top=0
frame = QWidget()
self.setCentralWidget(frame)
central = windowchrome.bordered_body(frame, top=0)
```

`top=0` only where a menu bar sits above the body. Give both the inset and you
get a colored line *between* the menu bar and the content instead of a border
around them.

A window that skips this comes out wearing the title bar's colors over its
whole surface — loud, but not broken. `QMessageBox` is usually left that way
deliberately: it is transient, and there is no layout of yours to inset.

### 4. `menu_bar_style()` — into any `QMenuBar` stylesheet

```python
def menu_style() -> str:
    return f"""
        QMenuBar::item {{ padding: 8px 16px; background: transparent; }}
        ...
    """ + windowchrome.menu_bar_style()
```

This is what insets the menu bar inside the border. Do not write the
`QMenuBar { margin: ... }` rule yourself — see gotcha 2.

### 5. `body_window_color()` / `body_text_color()` — replace every palette read of `Window` and `WindowText`

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

## 5. The gotchas

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

The filter acts on `QEvent.Polish` **and** `QEvent.StyleChange`. Polish alone
is one pass per widget and misses the subtree beneath a later-styled ancestor
(a splitter styled after both its panes have been polished). There is no loop
between the two: `setPalette` raises `PaletteChange`, which is not a trigger.

**The symptom to recognise:** a widget wearing the title bar color *only while
the window has focus*. Only the `Active` group is repurposed, so anything
leaking reverts to the theme's gray the moment the window is defocused.

### 2. `QMenuBar` ignores vertical margins and applies horizontal ones to its height

Measured in isolation: a 20px horizontal margin takes a 23px bar to 63px;
`margin-top` or `margin-bottom` alone changes nothing at all. That quirk is
*load-bearing* — it is what insets the bar on all four sides. So
`menu_bar_style()` sets only the horizontal pair, and the vertical properties
would be decoration on a rule Qt discards.

Note also that `QMainWindow` lays the bar out itself, so the margin never moves
the bar's geometry, only what it paints inside it: the color showing through is
the **window's** background, not the bar's. That is why
`window_border_style()` carries a `QMainWindow` rule, and why the bar's own
background has to be restated in `menu_bar_style()`.

### 3. Never derive a body color from `QApplication.palette()`

The `Window` and `WindowText` roles carry the *title bar's* colors once
`install()` has run, so a derived color comes out tinted — and, where it
lightens or darkens what it read, wrong twice over. One host app's splitter
handle did exactly this: it read the title bar blue and lightened it, painting
the handle a *brighter* blue than the bar. Another computed its muted help text
from `WindowText` and would have drawn it in the title bar's white.
`body_window_color()` and `body_text_color()` are the fix and the rule.

### 4. One rule covers dialogs too

`QWidget#windowFrame` matches a `QDialog` as well as a plain `QWidget` — Qt
type selectors match subclasses, unlike CSS. That is why a single
`window_border_style()` covers the main window and every dialog.

### 5. The decoration plugin choice is silent when wrong

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

### 6. `bordered_body()` keeps a stylesheet the window already has — but only one set before it

The call puts its three border rules in *front* of whatever the window's
stylesheet already holds, so an application whose window styles itself keeps
that styling and the host's rules still win any tie of equal specificity. What
it cannot survive is the reverse order: `setStyleSheet()` replaces rather than
appends, so a window that sets its own sheet *after* `bordered_body()` throws
the border away with it. Call `bordered_body()` last.

The related trap is `setObjectName()`. `bordered_body()` names the widget you
pass it `windowFrame`, so a window that relies on an object name of its own —
for a `QWidget#myWindow[state="..."]` rule, say — must not be passed in
directly: give the content its own widget inside the returned body and put the
name on that.

## 6. How to verify an integration

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

**The border actually paints.** `grab()` renders under
`QT_QPA_PLATFORM=offscreen`, so border pixels can be sampled directly without a
display:

```python
import os, sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import windowchrome
from yourapp.style import APP_THEME, tune_palette

windowchrome.configure(APP_THEME)
app = QApplication(sys.argv)
tune_palette(app)
windowchrome.install(app)

from yourapp.window import MainWindow
w = MainWindow(); w.resize(1000, 640); w.show()

def report():
    N = APP_THEME.border_width
    img = w.grab().toImage(); h = img.height()
    print("expect border", APP_THEME.title_bg,
          "| body", windowchrome.body_window_color().name())
    print(f"left={img.pixelColor(N // 2, h - N - 20).name()} "
          f"right={img.pixelColor(img.width() - 1 - N // 2, h - N - 20).name()} "
          f"bottom={img.pixelColor(img.width() // 2, h - 1 - N // 2).name()} "
          f"| inside={img.pixelColor(N + 3, h - N - 20).name()}")
    app.quit()

QTimer.singleShot(1200, report)
app.exec()
```

The three border samples must equal `title_bg` and `inside` must equal the body
color. Run the same over every dialog: a dialog that skipped step 3 shows the
body color where the border should be.

**By eye:** run the app. Colored title bar, a border of `border_width` on all
four sides, and a menu bar inset *within* that border rather than flush to the
window edge.

## 7. Troubleshooting

| Symptom | Cause |
| --- | --- |
| Gray title bar, border fine | `configure()` ran after `QApplication`, or `decoration` names a plugin Qt does not ship (it falls back to `adwaita` silently). Check `/proc/self/maps`. |
| Gray title bar, no warning, not Wayland | Expected. The title bar is out-of-process under X11; only the border is yours. Check `app.platformName()`. |
| A widget is colored like the title bar, but **only when focused** | A palette leak: `install()` was not called, or was called before the app's own palette tuning. Only the `Active` group is repurposed, which is why defocusing reverts it. |
| A whole window is colored like the title bar | That window never called `bordered_body()`. |
| Border missing on one dialog | Same: that dialog never called `bordered_body()`, or built into the widget it passed in rather than the one returned. |
| A derived color (splitter, handle, hover) comes out tinted with the title bar | Something still reads `QApplication.palette()` for `Window`. Use `body_window_color()`. |
| Menu bar flush to the window edge | `menu_bar_style()` not concatenated into the menu stylesheet. |
| The window's own stylesheet stopped working after integrating | The window called `setStyleSheet()` *after* `bordered_body()`, replacing the border rules — or it relied on an object name that `bordered_body()` overwrote with `windowFrame`. See gotcha 6. |
| Muted/derived text is white and unreadable on the body | Something reads `QApplication.palette()` for `WindowText`. Use `body_text_color()`. |
| Menu bar is suddenly ~3x taller | Expected and load-bearing: `QMenuBar` applies horizontal margins to its height. That is what insets it vertically. |
| A colored line between the menu bar and the content | The main window's `bordered_body()` was not given `top=0`. |
