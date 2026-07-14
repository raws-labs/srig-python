"""High-level Board convenience wrapper."""

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from siliconrig.client import Client
from siliconrig.session import Session


class Board:
    """Convenience wrapper that creates a client, session, and flashes firmware.

    Designed for concise pytest fixtures::

        @pytest.fixture
        def board():
            with Board("esp32-s3", firmware="build/app.bin") as b:
                yield b

        def test_boot(board):
            assert board.expect("Ready", timeout=5)

    Serial methods (``send``, ``read``, ``read_until``, ``expect``, ``flush``)
    are available directly on the Board instance for convenience.
    """

    def __init__(
        self,
        board_type: str,
        firmware: str | Path | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._board_type = board_type
        self._firmware = firmware
        self._api_key = api_key
        self._base_url = base_url
        self._client: Client | None = None
        self._session: Session | None = None
        self._ctx: Any = None

    def __enter__(self) -> Self:
        self._client = Client(api_key=self._api_key, base_url=self._base_url)
        self._ctx = self._client.session(board=self._board_type)
        self._session = self._ctx.__enter__()

        if self._firmware:
            self._session.flash(self._firmware)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._ctx:
            self._ctx.__exit__(exc_type, exc_val, exc_tb)
        if self._client:
            self._client.close()

    # -- proxied serial methods -----------------------------------------------

    def send(self, data: str) -> None:
        """Send data to the board's UART."""
        assert self._session is not None
        self._session.serial.send(data)

    def read(self, n: int = 4096, timeout: float = 5.0) -> str:
        """Read up to *n* characters."""
        assert self._session is not None
        return self._session.serial.read(n, timeout=timeout)

    def read_until(self, pattern: str, timeout: float = 10.0) -> str:
        """Read until *pattern* appears."""
        assert self._session is not None
        return self._session.serial.read_until(pattern, timeout=timeout)

    def expect(self, pattern: str, timeout: float = 10.0) -> str:
        """Assert that *pattern* appears within *timeout* seconds."""
        assert self._session is not None
        return self._session.serial.expect(pattern, timeout=timeout)

    def flush(self) -> None:
        """Clear the serial receive buffer."""
        assert self._session is not None
        self._session.serial.flush()

    # -- proxied session methods ----------------------------------------------

    def flash(self, firmware: str | Path, timeout: float = 300.0) -> None:
        """Flash firmware to the board."""
        assert self._session is not None
        self._session.flash(firmware, timeout=timeout)

    def reset(self) -> None:
        """Power-cycle the board."""
        assert self._session is not None
        self._session.reset()

    def info(self) -> dict[str, Any]:
        """Get session details."""
        assert self._session is not None
        return self._session.info()

    @property
    def serial(self):
        """Access the underlying Serial instance."""
        assert self._session is not None
        return self._session.serial

    @property
    def session(self) -> Session:
        """Access the underlying Session instance."""
        assert self._session is not None
        return self._session
