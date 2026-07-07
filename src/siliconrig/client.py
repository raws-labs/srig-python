"""siliconrig API client."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx

from siliconrig.exceptions import AuthError, SessionError
from siliconrig.session import Session

DEFAULT_BASE_URL = "https://api.srig.io"
DEFAULT_TIMEOUT = 30.0


class Client:
    """Client for the siliconrig REST API.

    Args:
        api_key: API key (``key_...``). Falls back to
            the ``SRIG_API_KEY`` environment variable.
        base_url: Coordinator base URL. Falls back to ``SRIG_BASE_URL``
            or ``https://api.srig.io``.
        timeout: Default HTTP timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key or os.environ.get("SRIG_API_KEY")
        if not self.api_key:
            raise AuthError(
                "No API key provided. Pass api_key= or set SRIG_API_KEY."
            )

        self.base_url = (
            base_url or os.environ.get("SRIG_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")

        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=timeout,
        )

    # -- public helpers -------------------------------------------------------

    def boards(self) -> list[dict[str, Any]]:
        """List available board types with real-time availability."""
        resp = self._http.get("/v1/boards")
        _check(resp)
        return resp.json()

    @contextmanager
    def session(
        self,
        board: str,
        base_image_id: str | None = None,
    ) -> Generator[Session, None, None]:
        """Create a hardware session and yield it as a context manager.

        The session is automatically ended when the block exits.

        Args:
            board: Board type identifier (e.g. ``"esp32-s3"``).
            base_image_id: Optional base image to pre-flash.
        """
        body: dict[str, Any] = {"board_type": board}
        if base_image_id:
            body["base_image_id"] = base_image_id

        resp = self._http.post("/v1/sessions", json=body)
        _check(resp)
        data = resp.json()
        session_id: str = data["id"]

        session = Session(
            session_id=session_id,
            data=data,
            http=self._http,
            base_url=self.base_url,
            api_key=self.api_key,
        )
        try:
            yield session
        finally:
            session.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()


def _check(resp: httpx.Response) -> None:
    """Raise a typed exception for non-2xx responses."""
    if resp.is_success:
        return
    try:
        detail = resp.json().get("error", resp.text)
    except Exception:
        detail = resp.text
    if resp.status_code in (401, 403):
        raise AuthError(detail)
    raise SessionError(f"[{resp.status_code}] {detail}")
