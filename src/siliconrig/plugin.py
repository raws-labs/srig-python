"""pytest plugin — auto-registered via the ``pytest11`` entry point.

Provides the ``siliconrig_board`` fixture and CLI options.
"""

import pytest

from siliconrig.board import Board


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("siliconrig", "siliconrig hardware-in-the-loop testing")
    group.addoption(
        "--siliconrig-board",
        dest="siliconrig_board",
        default=None,
        help="Board type to use for siliconrig sessions (e.g. esp32-s3).",
    )
    group.addoption(
        "--siliconrig-firmware",
        dest="siliconrig_firmware",
        default=None,
        help="Path to firmware binary to flash before tests.",
    )
    group.addoption(
        "--siliconrig-api-key",
        dest="siliconrig_api_key",
        default=None,
        help="API key (overrides SRIG_API_KEY env var).",
    )
    group.addoption(
        "--siliconrig-base-url",
        dest="siliconrig_base_url",
        default=None,
        help="Coordinator base URL (overrides SRIG_BASE_URL env var).",
    )


@pytest.fixture(scope="session")
def siliconrig_board(request: pytest.FixtureRequest):
    """Session-scoped fixture that provides a flashed, ready-to-use board.

    Configure via CLI options or environment variables::

        pytest --siliconrig-board esp32-s3 --siliconrig-firmware build/app.bin

    Or use the ``Board`` class directly in your own fixtures for more control.
    """
    board_type = request.config.getoption("siliconrig_board")
    if board_type is None:
        pytest.skip("No --siliconrig-board specified; skipping HIL tests")

    firmware = request.config.getoption("siliconrig_firmware")
    api_key = request.config.getoption("siliconrig_api_key")
    base_url = request.config.getoption("siliconrig_base_url")

    with Board(
        board_type,
        firmware=firmware,
        api_key=api_key,
        base_url=base_url,
    ) as board:
        yield board
