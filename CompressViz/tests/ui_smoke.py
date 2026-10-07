"""Headless smoke test for the Streamlit user interface."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest


def main() -> None:
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
    app.run()
    if app.exception:
        raise AssertionError(app.exception)
    if not app.title or app.title[0].value != "CompressViz":
        raise AssertionError("The main UI did not render")
    if len(app.tabs) != 6:
        raise AssertionError(f"Expected 6 UI tabs, got {len(app.tabs)}")
    algorithm = next(widget for widget in app.selectbox if len(widget.options) == 7)
    for label in algorithm.options:
        algorithm.select(label)
        app.run()
        if app.exception:
            raise AssertionError(f"UI failed for {label}: {app.exception}")
        algorithm = next(widget for widget in app.selectbox if len(widget.options) == 7)
    print("Streamlit UI smoke test passed for all 7 algorithms")


if __name__ == "__main__":
    main()
