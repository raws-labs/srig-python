# siliconrig

Python SDK for [siliconrig](https://siliconrig.dev) — remote access to real embedded boards.

Use it in scripts, automation, or as a pytest plugin for hardware-in-the-loop testing.

## Install

```bash
pip install siliconrig
```

## Quick start

```python
from siliconrig import Client

client = Client()

with client.session(board="esp32-s3") as session:
    session.flash("firmware.bin")
    session.serial.expect("Ready", timeout=10)
    session.serial.send("status\n")
    print(session.serial.read_until("OK", timeout=5))
```

Or use the `Board` shorthand:

```python
from siliconrig import Board

with Board("esp32-s3", firmware="build/app.bin") as board:
    board.expect("System ready", timeout=5)
    board.send("gpio set 4 1\n")
    board.expect("GPIO4=HIGH", timeout=2)
```

## Firmware formats

`flash()` accepts a raw `.bin` (all boards), a `.uf2` (rp2350), or — for STM32
boards — an `.elf` or Intel `.hex`, which siliconrig converts to a raw image
server-side before flashing. Hand it your build's ELF directly:

```python
with Board("stm32-h753", firmware="build/firmware.elf") as board:
    board.expect("All tests passed", timeout=30)
```

## pytest plugin

The package includes a pytest plugin that registers automatically. Use it with custom fixtures:

```python
import pytest
from siliconrig import Board

@pytest.fixture
def board():
    with Board("esp32-s3", firmware="build/app.bin") as b:
        yield b

def test_boot_ok(board):
    assert board.expect("System ready", timeout=5)
```

Or use the built-in `siliconrig_board` fixture via CLI options:

```bash
pytest --siliconrig-board esp32-s3 --siliconrig-firmware build/app.bin tests/hil/
```

## Authentication

Set your API key via environment variable:

```bash
export SRIG_API_KEY=key_...
```

Or pass it directly:

```python
client = Client(api_key="key_...")
```

## Documentation

- [Python SDK guide](https://siliconrig.dev/docs/guides/python-sdk)
- [CI/CD integration](https://siliconrig.dev/docs/guides/cicd)
