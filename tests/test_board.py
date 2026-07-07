"""Tests for siliconrig.Board convenience wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from siliconrig.board import Board


class TestBoardContextManager:
    @patch("siliconrig.board.Client")
    def test_creates_session_and_flashes(self, MockClient):
        mock_client = MockClient.return_value
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_client.session.return_value = mock_ctx

        with Board("esp32-s3", firmware="app.bin", api_key="sk_test") as b:
            assert b.session is mock_session
            mock_session.flash.assert_called_once_with("app.bin")

        mock_client.close.assert_called_once()

    @patch("siliconrig.board.Client")
    def test_no_firmware_skips_flash(self, MockClient):
        mock_client = MockClient.return_value
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_client.session.return_value = mock_ctx

        with Board("esp32-s3", api_key="sk_test") as b:
            pass

        mock_session.flash.assert_not_called()


class TestBoardProxies:
    @patch("siliconrig.board.Client")
    def test_send_proxies_to_serial(self, MockClient):
        mock_client = MockClient.return_value
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_client.session.return_value = mock_ctx

        with Board("esp32-s3", api_key="sk_test") as b:
            b.send("test\n")
            mock_session.serial.send.assert_called_with("test\n")

            b.expect("OK")
            mock_session.serial.expect.assert_called_with("OK", timeout=10.0)

            b.flush()
            mock_session.serial.flush.assert_called_once()

            b.reset()
            mock_session.reset.assert_called_once()
