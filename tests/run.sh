#!/usr/bin/env bash
# Run the test suite. Takes the same arguments pytest does:
#
#   ./tests/run.sh                              everything
#   ./tests/run.sh tests/test_markdownview.py   one file
#   ./tests/run.sh -k anchor -v                 by name, verbosely
#
# pytest and pytest-qt are pulled in by `uv run --with` rather than declared
# in pyproject.toml, so nothing has to be set up before this works and the
# package's own dependency stays the one it actually ships with.
#
# QT_QPA_PLATFORM=offscreen is what lets the widget tests run without a
# display. Note that a widget must still be shown and resized under it or
# every scroll bar reads 0 — see conftest.
set -euo pipefail
cd "$(dirname "$0")/.."
QT_QPA_PLATFORM=offscreen exec uv run --with pytest --with pytest-qt pytest "${@:-tests}"
