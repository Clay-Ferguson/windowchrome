"""The two-document fixture every markdown test reads.

Built into `tmp_path` rather than checked in: what makes these documents
interesting is a heading repeated verbatim, a link to a file that is not
there, and an image wider than any window — none of which reads as anything
but a mistake sitting in a repository.
"""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor, QImage

from windowchrome import close_markdown_windows

# Enough filler that the documents are taller than any test window, so
# "did it scroll" is a question with an answer.
FILLER = "\n\n".join(f"Filler paragraph {n}." for n in range(60))

# Wider than the widths any test fits images to.
WIDE_IMAGE = (1200, 900)
SMALL_IMAGE = (40, 30)

A_MD = f"""# Alpha Guide

- [Second](#second)
- [Over there](b.md)
- [Deep in there](b.md#beta-heading)
- [Missing](gone.md)
- [Outside](https://example.com/x)

## Second

{FILLER}

## Repeat

First one.

## Repeat

Second one.

## Pictures

![wide]({{wide}})

![small]({{small}})

```python
x = 1
```
"""

B_MD = """# Beta

## Beta Heading

[Back to alpha](a.md#second)
"""


@pytest.fixture
def docs(tmp_path, qapp):
    """A directory holding `a.md`, `b.md` and the two images they show."""
    for name, size in (("wide.png", WIDE_IMAGE), ("small.png", SMALL_IMAGE)):
        image = QImage(*size, QImage.Format.Format_RGB32)
        image.fill(QColor("#3366aa"))
        assert image.save(str(tmp_path / name))

    (tmp_path / "a.md").write_text(A_MD.format(wide="wide.png", small="small.png"))
    (tmp_path / "b.md").write_text(B_MD)
    return tmp_path


@pytest.fixture
def shown(qtbot):
    """Show and size a widget, and hand it to pytest-qt to clean up.

    Load-bearing, not ceremony: under `QT_QPA_PLATFORM=offscreen` a widget
    that was never shown and resized has no layout, so every scroll bar
    reports a maximum of 0 and every "did it scroll" assertion passes
    without testing anything.
    """

    def show(widget, width=800, height=600):
        qtbot.addWidget(widget)
        widget.resize(width, height)
        widget.show()
        qtbot.waitExposed(widget)
        return widget

    return show


@pytest.fixture(autouse=True)
def _close_windows():
    """Empty the dialog registry between tests.

    It is module state, so without this a window left open by one test is
    the window a later test is handed back when it asks for a new one.
    """
    yield
    close_markdown_windows()
