# srig-python

Python SDK and pytest plugin for SiliconRig: open a session on a remote board, flash firmware, and drive its serial console from scripts or tests. httpx plus websockets; hatchling with hatch-vcs. Public, github.com/raws-labs/srig-python; PyPI package `siliconrig`.

## Build, test, run
- `pip install -e ".[dev]"`: editable install with pytest, pytest-asyncio, ruff.
- `pytest tests/ -v`: unit tests, fully offline (a FakeWebSocket and a mocked httpx client in `tests/conftest.py`); no API key or hardware needed.
- `ruff check src tests`: lint; line length 99, target py310 (config in pyproject).
- `python -m build`: sdist and wheel. The version comes from the git tag via hatch-vcs; an untagged checkout builds a `.devN` version, which is why CI checks out with `fetch-depth: 0`.
- Release: tag `vX.Y.Z`, then create a GitHub Release (`gh release create vX.Y.Z`). `.github/workflows/publish.yml` runs on the Release "published" event, not on tag push, and uploads through PyPI trusted publishing (environment `pypi`).

## Layout
- `src/siliconrig/client.py`: `Client` (httpx, sends the key as `X-API-Key`) and the `Client.session(board)` context manager.
- `session.py`: `Session` with `flash()`, `reset()` (power-cycle), `info()`, `close()`. `serial.py`: `Serial`, a WebSocket reader thread exposing `send`, `read`, `read_until`, `expect`, `flush`.
- `board.py`: `Board(board_type, firmware=...)`, the wrapper meant for fixtures; proxies the serial and session methods.
- `plugin.py`: pytest plugin registered through the `pytest11` entry point; adds `--siliconrig-board`, `--siliconrig-firmware`, `--siliconrig-api-key`, `--siliconrig-base-url` and the session-scoped `siliconrig_board` fixture (skips when no board is given).

## Conventions
- Config: `api_key` or `SRIG_API_KEY`; `base_url` or `SRIG_BASE_URL`, default `https://api.srig.io`. Endpoints live under `/v1/`; the serial socket is `/v1/sessions/{id}/serial`.
- Board types are plain strings (`esp32-s3`, `stm32-h753`, `stm32-f446`, `rp2350`). `flash()` takes `.bin` for all boards, `.uf2` for rp2350, and `.elf` or `.hex` for STM32 boards (converted server-side).
- Exceptions derive from `SiliconrigError`: `AuthError` (401/403), `SessionError`, `FlashError`, `SerialTimeout`.

## Gotchas
- Flash completion is signaled by a `flash_done` frame on the serial WebSocket, not by session state. `Session` opens the serial socket eagerly, which already marks the session active, so polling state returns before the hardware has finished flashing. `flash()` therefore calls `Serial.arm_flash()` before the upload, waits for the frame, then `flush()`es pre-flash noise; keep that order.
- Serial frames are JSON `{"type": "serial_data", "data": <base64>}` in both directions. `read_until` returns through the match and pushes the remainder back into the buffer.
- Default flash timeout is 300 s because multi-MB images take minutes on real hardware; the server bounds a stuck flash earlier than that.

## Open
- `board.py` imports `typing.Self` (Python 3.11+) while pyproject declares `requires-python >= 3.10` (verify which is intended).
