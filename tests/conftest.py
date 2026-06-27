"""Shared test fixtures."""

import json
import threading
from unittest.mock import MagicMock, patch

import pytest


class FakeWebSocket:
    """Simulates a WebSocket connection for serial testing."""

    def __init__(self):
        self._inbox: list[str] = []
        self._sent: list[str] = []
        self._closed = False
        self._lock = threading.Lock()

    def inject(self, msg_type: str, data: str) -> None:
        with self._lock:
            self._inbox.append(json.dumps({"type": msg_type, "data": data}))

    def inject_raw(self, obj: dict) -> None:
        """Inject an arbitrary frame (e.g. flash_done with success/error)."""
        with self._lock:
            self._inbox.append(json.dumps(obj))

    def send(self, data: str) -> None:
        self._sent.append(data)

    def close(self, timeout: float = 3) -> None:
        self._closed = True

    def __iter__(self):
        while not self._closed:
            with self._lock:
                if self._inbox:
                    yield self._inbox.pop(0)


@pytest.fixture
def fake_ws():
    return FakeWebSocket()


@pytest.fixture
def mock_http():
    """A mocked httpx.Client that returns canned responses."""
    client = MagicMock()

    def make_response(status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.is_success = 200 <= status_code < 300
        resp.json.return_value = json_data or {}
        resp.text = json.dumps(json_data or {})
        return resp

    client._make_response = make_response
    return client
