import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


import tkinter  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def tk_root():
    """One Tk root for the whole test session. Repeatedly creating and
    destroying roots in a single process is flaky (occasional TclError), so
    every GUI test module shares this one and builds its widgets inside it."""
    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except tkinter.TclError:
        pytest.skip("no display available for Tk")
    root.geometry("1500x700")
    yield root
    root.destroy()
