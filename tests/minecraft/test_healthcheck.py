import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from minecraft.healthcheck import (
    HealthStatus,
    CHECK_LABELS,
    check_tcp_connect,
    check_udp_minecraft_bedrock,
    check_systemd_service,
    run_all_checks,
    format_summary,
    format_alert,
    run_healthcheck,
    run_daily_summary,
    run_on_demand_check,
    _format_status_line,
    _format_change_line,
)
import minecraft.healthcheck as healthcheck_module


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level state between tests."""
    healthcheck_module._previous_status = None
    yield
    healthcheck_module._previous_status = None


class TestHealthStatus:
    def test_dataclass_fields(self):
        ts = datetime(2026, 2, 8, 12, 0, 0)
        s = HealthStatus(True, False, True, False, True, ts)
        assert s.java_local is True
        assert s.bedrock_local is False
        assert s.playit_service is True
        assert s.java_tunnel is False
        assert s.bedrock_tunnel is True
        assert s.timestamp == ts

    def test_check_labels_match_dataclass(self):
        ts = datetime.now()
        s = HealthStatus(True, True, True, True, True, ts)
        for field, _ in CHECK_LABELS:
            assert hasattr(s, field)


class TestCheckTcpConnect:
    @patch("minecraft.healthcheck.socket.create_connection")
    def test_returns_true_on_success(self, mock_conn):
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert check_tcp_connect("localhost", 25565) is True

    @patch("minecraft.healthcheck.socket.create_connection", side_effect=OSError)
    def test_returns_false_on_os_error(self, mock_conn):
        assert check_tcp_connect("localhost", 25565) is False

    @patch("minecraft.healthcheck.socket.create_connection", side_effect=TimeoutError)
    def test_returns_false_on_timeout(self, mock_conn):
        assert check_tcp_connect("localhost", 25565) is False


class TestCheckUdpMinecraftBedrock:
    @patch("minecraft.healthcheck.socket.socket")
    def test_returns_true_on_valid_pong(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        # 0x1C is the Unconnected Pong packet ID
        mock_sock.recvfrom.return_value = (b"\x1c" + b"\x00" * 50, ("127.0.0.1", 19132))
        assert check_udp_minecraft_bedrock("localhost", 19132) is True
        mock_sock.close.assert_called_once()

    @patch("minecraft.healthcheck.socket.socket")
    def test_returns_false_on_wrong_packet_id(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"\x00" + b"\x00" * 50, ("127.0.0.1", 19132))
        assert check_udp_minecraft_bedrock("localhost", 19132) is False
        mock_sock.close.assert_called_once()

    @patch("minecraft.healthcheck.socket.socket")
    def test_returns_false_on_timeout(self, mock_socket_cls):
        import socket as real_socket
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recvfrom.side_effect = real_socket.timeout
        assert check_udp_minecraft_bedrock("localhost", 19132) is False
        mock_sock.close.assert_called_once()

    @patch("minecraft.healthcheck.socket.socket")
    def test_returns_false_on_os_error(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.sendto.side_effect = OSError
        assert check_udp_minecraft_bedrock("localhost", 19132) is False
        mock_sock.close.assert_called_once()

    @patch("minecraft.healthcheck.socket.socket")
    def test_returns_false_on_empty_response(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.recvfrom.return_value = (b"", ("127.0.0.1", 19132))
        assert check_udp_minecraft_bedrock("localhost", 19132) is False


class TestCheckSystemdService:
    @patch("minecraft.healthcheck.subprocess.run")
    def test_returns_true_when_active(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_systemd_service("playit.service") is True

    @patch("minecraft.healthcheck.subprocess.run")
    def test_returns_false_when_inactive(self, mock_run):
        mock_run.return_value = MagicMock(returncode=3)
        assert check_systemd_service("playit.service") is False

    @patch("minecraft.healthcheck.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_false_when_systemctl_missing(self, mock_run):
        assert check_systemd_service("playit.service") is False

    @patch("minecraft.healthcheck.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=10))
    def test_returns_false_on_timeout(self, mock_run):
        assert check_systemd_service("playit.service") is False


class TestFormatStatusLine:
    def test_ok_line(self):
        line = _format_status_line("Java (local)", True)
        assert "✅" in line
        assert "Java (local)" in line
        assert "OK" in line

    def test_down_line(self):
        line = _format_status_line("Java (local)", False)
        assert "❌" in line
        assert "DOWN" in line


class TestFormatChangeLine:
    def test_went_down(self):
        line = _format_change_line("Java tunnel", False, True)
        assert "❌" in line
        assert "DOWN (was UP)" in line

    def test_came_back_up(self):
        line = _format_change_line("Java tunnel", True, False)
        assert "✅" in line
        assert "OK (was DOWN)" in line

    def test_stayed_ok(self):
        line = _format_change_line("Java tunnel", True, True)
        assert "✅" in line
        assert "OK" in line
        assert "was" not in line

    def test_stayed_down(self):
        line = _format_change_line("Java tunnel", False, False)
        assert "❌" in line
        assert "DOWN" in line
        assert "was" not in line


class TestFormatSummary:
    def test_all_ok_has_green_header(self):
        s = HealthStatus(True, True, True, True, True, datetime(2026, 2, 8, 14, 30, 0))
        msg = format_summary(s)
        assert "🟢" in msg
        assert "Minecraft Server Status" in msg
        assert "Last checked: 2026-02-08 14:30:00" in msg

    def test_some_down_has_red_header(self):
        s = HealthStatus(False, True, True, True, True, datetime(2026, 2, 8, 14, 30, 0))
        msg = format_summary(s)
        assert "🔴" in msg

    def test_contains_all_checks(self):
        s = HealthStatus(True, False, True, False, True, datetime.now())
        msg = format_summary(s)
        assert "Java (local)" in msg
        assert "Bedrock (local)" in msg
        assert "playit.service" in msg
        assert "Java tunnel" in msg
        assert "Bedrock tunnel" in msg


class TestFormatAlert:
    def test_alert_header(self):
        prev = HealthStatus(True, True, True, True, True, datetime.now())
        curr = HealthStatus(False, True, True, True, True, datetime.now())
        msg = format_alert(curr, prev)
        assert "🚨" in msg
        assert "Minecraft Server Alert" in msg

    def test_shows_changes(self):
        prev = HealthStatus(True, True, True, True, True, datetime.now())
        curr = HealthStatus(False, True, True, False, True, datetime.now())
        msg = format_alert(curr, prev)
        assert "DOWN (was UP)" in msg


class TestRunAllChecks:
    @patch("minecraft.healthcheck.check_udp_minecraft_bedrock", return_value=True)
    @patch("minecraft.healthcheck.check_tcp_connect", return_value=True)
    @patch("minecraft.healthcheck.check_systemd_service", return_value=True)
    def test_returns_health_status(self, mock_systemd, mock_tcp, mock_udp):
        status = run_all_checks()
        assert isinstance(status, HealthStatus)
        assert status.java_local is True
        assert status.bedrock_local is True
        assert status.playit_service is True
        assert status.java_tunnel is True
        assert status.bedrock_tunnel is True
        assert isinstance(status.timestamp, datetime)


class TestRunHealthcheck:
    @patch("minecraft.healthcheck.send_message_to_me")
    @patch("minecraft.healthcheck.run_all_checks")
    def test_first_run_no_message(self, mock_checks, mock_send):
        mock_checks.return_value = HealthStatus(True, True, True, True, True, datetime.now())
        run_healthcheck()
        mock_send.assert_not_called()

    @patch("minecraft.healthcheck.send_message_to_me")
    @patch("minecraft.healthcheck.run_all_checks")
    def test_no_change_no_message(self, mock_checks, mock_send):
        status = HealthStatus(True, True, True, True, True, datetime.now())
        mock_checks.return_value = status
        run_healthcheck()  # first run
        run_healthcheck()  # second run - no change
        mock_send.assert_not_called()

    @patch("minecraft.healthcheck.send_message_to_me")
    @patch("minecraft.healthcheck.run_all_checks")
    def test_state_change_sends_alert(self, mock_checks, mock_send):
        mock_checks.return_value = HealthStatus(True, True, True, True, True, datetime.now())
        run_healthcheck()  # first run

        mock_checks.return_value = HealthStatus(False, True, True, True, True, datetime.now())
        run_healthcheck()  # state change
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "Alert" in msg
        assert "DOWN (was UP)" in msg


class TestRunDailySummary:
    @patch("minecraft.healthcheck.send_message_to_me")
    @patch("minecraft.healthcheck.run_all_checks")
    def test_sends_summary(self, mock_checks, mock_send):
        mock_checks.return_value = HealthStatus(True, True, True, True, True, datetime.now())
        run_daily_summary()
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "Minecraft Server Status" in msg


class TestRunOnDemandCheck:
    @patch("minecraft.healthcheck.run_all_checks")
    def test_returns_formatted_summary(self, mock_checks):
        mock_checks.return_value = HealthStatus(True, True, True, True, True, datetime.now())
        result = run_on_demand_check()
        assert "Minecraft Server Status" in result
        assert "🟢" in result
