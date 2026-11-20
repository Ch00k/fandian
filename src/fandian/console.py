"""A spinner for the steps that wait on the network or on Docker. Without a terminal (output
piped, say) it draws nothing."""

import itertools
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager

_FRAMES = "|/-\\"
_CLEAR_LINE = "\r\033[K"


@contextmanager
def working(text: str) -> Generator[None]:
    """Show a spinner with `text` while the block runs."""
    if not sys.stdout.isatty():
        yield
        return

    done = threading.Event()

    def spin() -> None:
        for frame in itertools.cycle(_FRAMES):
            sys.stdout.write(f"{_CLEAR_LINE}{frame} {text}")
            sys.stdout.flush()
            if done.wait(0.1):
                return

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        sys.stdout.write(_CLEAR_LINE)
        sys.stdout.flush()
