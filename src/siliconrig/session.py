"""Hardware session wrapper."""

from pathlib import Path
from typing import Any

import httpx

from siliconrig.exceptions import FlashError, SessionError
from siliconrig.serial import Serial
from siliconrig.exceptions import SerialTimeout

_FLASH_DEFAULT_TIMEOUT = 120.0


class Session:
    """A live session on a remote board.

    Created via :meth:`Client.session` — not instantiated directly.
    """

    def __init__(
        self,
        session_id: str,
        data: dict[str, Any],
        http: httpx.Client,
        base_url: str,
        api_key: str,
    ) -> None:
        self.id = session_id
        self._data = data
        self._http = http
        self._api_key = api_key
        self._closed = False

        ws_scheme = "wss" if base_url.startswith("https") else "ws"
        ws_base = base_url.replace("https://", "").replace("http://", "")
        ws_url = f"{ws_scheme}://{ws_base}/v1/sessions/{session_id}/serial"

        self.serial = Serial(ws_url, api_key)

    # -- firmware -------------------------------------------------------------

    def flash(
        self,
        firmware: str | Path,
        timeout: float = _FLASH_DEFAULT_TIMEOUT,
    ) -> None:
        """Upload and flash a firmware binary.

        Args:
            firmware: Path to the ``.bin`` file (max 4 MB).
            timeout: Seconds to wait for flashing to complete.

        Raises:
            FlashError: If flashing fails or times out.
            FileNotFoundError: If the firmware file doesn't exist.
        """
        path = Path(firmware)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {path}")

        # Arm flash-completion tracking on the serial WS *before* uploading, so
        # we can't miss a fast flash_done. Flashing is async: the coordinator
        # ACKs the upload immediately and the pod signals real completion with a
        # flash_done frame on the serial connection (same as the Go CLI does).
        self.serial.arm_flash()

        with open(path, "rb") as f:
            resp = self._http.post(
                f"/v1/sessions/{self.id}/flash",
                files={"firmware": (path.name, f, "application/octet-stream")},
                timeout=timeout,
            )

        if not resp.is_success:
            try:
                detail = resp.json().get("error", resp.text)
            except Exception:
                detail = resp.text
            raise FlashError(f"Flash upload failed: {detail}")

        try:
            success, err = self.serial.wait_flash(timeout)
        except SerialTimeout as exc:
            raise FlashError(str(exc)) from exc
        if not success:
            raise FlashError(f"Flash failed: {err or 'unknown'}")

        # Discard any pre-flash / flashing-noise bytes so the next read/expect
        # sees only output from the freshly-flashed firmware's boot.
        self.serial.flush()

    # -- power ----------------------------------------------------------------

    def reset(self) -> None:
        """Power-cycle the board via USB hub port control."""
        resp = self._http.post(f"/v1/sessions/{self.id}/power-cycle")
        if not resp.is_success:
            raise SessionError(f"Power cycle failed: {resp.text}")

    # -- info -----------------------------------------------------------------

    def info(self) -> dict[str, Any]:
        """Fetch current session details from the coordinator."""
        resp = self._http.get(f"/v1/sessions/{self.id}")
        if not resp.is_success:
            raise SessionError(f"Failed to get session info: {resp.text}")
        self._data = resp.json()
        return self._data

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """End the session and disconnect serial."""
        if self._closed:
            return
        self._closed = True
        self.serial.close()
        try:
            self._http.delete(f"/v1/sessions/{self.id}")
        except Exception:
            pass
