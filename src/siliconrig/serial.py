"""Serial interface over WebSocket."""

import base64
import json
import re
import threading
import time
from collections import deque

import websockets.sync.client as ws_sync

from siliconrig.exceptions import SerialTimeout

_WS_CLOSE_TIMEOUT = 3


class Serial:
    """WebSocket-backed serial console for a siliconrig session.

    Connects to the coordinator's serial proxy and exposes a synchronous
    send/read/expect API suitable for pytest tests.
    """

    def __init__(self, ws_url: str, api_key: str) -> None:
        self._buf: deque[str] = deque()
        self._lock = threading.Lock()
        self._closed = False
        self._error: Exception | None = None

        # Flash completion is signalled by a ``flash_done`` frame on this same
        # serial WebSocket (the coordinator forwards it from the pod). We latch
        # it here so Session.flash() can wait for the real completion instead of
        # polling session state (which is already "active" and returns instantly).
        self._flash_event = threading.Event()
        self._flash_result: tuple[bool, str] | None = None

        headers = {"X-API-Key": api_key}
        self._ws = ws_sync.connect(ws_url, additional_headers=headers)

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # -- flash completion -----------------------------------------------------

    def arm_flash(self) -> None:
        """Reset flash-completion state; call immediately before uploading."""
        self._flash_result = None
        self._flash_event.clear()

    def wait_flash(self, timeout: float) -> tuple[bool, str]:
        """Block until a ``flash_done`` frame arrives on the serial WS.

        Returns ``(success, error_message)``. Raises :class:`SerialTimeout` if
        no ``flash_done`` is received within *timeout* seconds.
        """
        if not self._flash_event.wait(timeout):
            extra = ""
            if self._error is not None:
                extra = f" (reader thread died: {self._error})"
            raise SerialTimeout(
                f"flash did not complete within {timeout}s "
                f"(no flash_done received).{extra}"
            )
        return self._flash_result or (False, "no flash result")

    # -- write ----------------------------------------------------------------

    def send(self, data: str) -> None:
        """Send a string to the board's UART."""
        b64 = base64.b64encode(data.encode("utf-8")).decode("ascii")
        msg = json.dumps({"type": "serial_data", "data": b64})
        self._ws.send(msg)

    # -- read -----------------------------------------------------------------

    def read(self, n: int = 4096, timeout: float = 5.0) -> str:
        """Read up to *n* characters from the receive buffer.

        Blocks until at least one character is available or *timeout* expires.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._buf:
                    text = "".join(self._buf)
                    self._buf.clear()
                    return text[:n]
            time.sleep(0.05)
        raise SerialTimeout(f"No data received within {timeout}s")

    def read_until(self, pattern: str, timeout: float = 10.0) -> str:
        """Read until *pattern* appears in the accumulated output.

        Returns everything up to and including the matched text.
        Data after the match is preserved in the buffer for subsequent reads.
        """
        collected: list[str] = []
        deadline = time.monotonic() + timeout
        regex = re.compile(re.escape(pattern))

        while time.monotonic() < deadline:
            with self._lock:
                if self._buf:
                    collected.append("".join(self._buf))
                    self._buf.clear()

            full = "".join(collected)
            m = regex.search(full)
            if m:
                # Put unmatched remainder back into the buffer.
                remainder = full[m.end():]
                if remainder:
                    with self._lock:
                        self._buf.appendleft(remainder)
                return full[: m.end()]
            time.sleep(0.05)

        full = "".join(collected)
        extra = ""
        if self._error is not None:
            extra = f" (reader thread died: {self._error})"
        raise SerialTimeout(
            f"Pattern {pattern!r} not found within {timeout}s.{extra} "
            f"Received so far: {full[-200:]!r}"
        )

    def expect(self, pattern: str, timeout: float = 10.0) -> str:
        """Assert that *pattern* appears within *timeout* seconds.

        Returns the matched output (same as ``read_until``).
        Raises ``SerialTimeout`` on failure.
        """
        return self.read_until(pattern, timeout=timeout)

    def flush(self) -> None:
        """Discard all buffered receive data."""
        with self._lock:
            self._buf.clear()

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """Disconnect the WebSocket."""
        self._closed = True
        try:
            self._ws.close(timeout=_WS_CLOSE_TIMEOUT)
        except Exception:
            pass

    # -- internal -------------------------------------------------------------

    def _read_loop(self) -> None:
        """Background thread: read WebSocket frames into the buffer."""
        try:
            for raw in self._ws:
                if self._closed:
                    return
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                mtype = msg.get("type")
                if mtype == "serial_data":
                    raw_data = msg.get("data", "")
                    try:
                        text = base64.b64decode(raw_data).decode("utf-8", errors="replace")
                    except Exception:
                        text = raw_data
                    with self._lock:
                        self._buf.append(text)
                elif mtype == "flash_done":
                    self._flash_result = (
                        bool(msg.get("success", False)),
                        str(msg.get("error", "") or ""),
                    )
                    self._flash_event.set()
        except Exception as exc:
            if not self._closed:
                self._error = exc
