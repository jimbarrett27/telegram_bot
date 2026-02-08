import socket
import struct
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

from telegram_bot.telegram_bot import send_message_to_me
from util.logging_util import setup_logger

logger = setup_logger(__name__)

# Connection targets
JAVA_LOCAL_HOST = "localhost"
JAVA_LOCAL_PORT = 25565
BEDROCK_LOCAL_HOST = "localhost"
BEDROCK_LOCAL_PORT = 19132
JAVA_TUNNEL_HOST = "population-born.gl.joinmc.link"
JAVA_TUNNEL_PORT = 33862
BEDROCK_TUNNEL_HOST = "classic-uptown.gl.at.ply.gg"
BEDROCK_TUNNEL_PORT = 39031
PLAYIT_SERVICE_NAME = "playit.service"


@dataclass
class HealthStatus:
    java_local: bool
    bedrock_local: bool
    playit_service: bool
    java_tunnel: bool
    bedrock_tunnel: bool
    timestamp: datetime


# Module-level state tracking
_previous_status: HealthStatus | None = None


def check_tcp_connect(host: str, port: int, timeout: float = 5) -> bool:
    """Attempt a TCP socket connection. Returns True if successful."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def check_udp_minecraft_bedrock(host: str, port: int, timeout: float = 5) -> bool:
    """Send a RakNet unconnected ping and check for a pong response."""
    # RakNet Unconnected Ping packet:
    # 0x01 (1 byte) - packet ID
    # time (8 bytes, big-endian long)
    # magic (16 bytes) - RakNet offline message ID
    # client GUID (8 bytes, big-endian long)
    raknet_magic = (
        b"\x00\xff\xff\x00\xfe\xfe\xfe\xfe"
        b"\xfd\xfd\xfd\xfd\x12\x34\x56\x78"
    )
    ping_time = int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF
    client_guid = 0
    packet = struct.pack(">B", 0x01) + struct.pack(">Q", ping_time) + raknet_magic + struct.pack(">Q", client_guid)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(packet, (host, port))
        data, _ = sock.recvfrom(4096)
        # A valid pong starts with 0x1c (Unconnected Pong)
        return len(data) > 0 and data[0] == 0x1C
    except (OSError, socket.timeout):
        return False
    finally:
        sock.close()


def check_systemd_service(service_name: str) -> bool:
    """Check if a systemd service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_all_checks() -> HealthStatus:
    """Execute all healthchecks and return the combined status."""
    return HealthStatus(
        java_local=check_tcp_connect(JAVA_LOCAL_HOST, JAVA_LOCAL_PORT),
        bedrock_local=check_udp_minecraft_bedrock(BEDROCK_LOCAL_HOST, BEDROCK_LOCAL_PORT),
        playit_service=check_systemd_service(PLAYIT_SERVICE_NAME),
        java_tunnel=check_tcp_connect(JAVA_TUNNEL_HOST, JAVA_TUNNEL_PORT),
        bedrock_tunnel=check_udp_minecraft_bedrock(BEDROCK_TUNNEL_HOST, BEDROCK_TUNNEL_PORT),
        timestamp=datetime.now(),
    )


CHECK_LABELS = [
    ("java_local", "Java (local)"),
    ("bedrock_local", "Bedrock (local)"),
    ("playit_service", "playit.service"),
    ("java_tunnel", "Java tunnel"),
    ("bedrock_tunnel", "Bedrock tunnel"),
]


def _format_status_line(label: str, is_ok: bool) -> str:
    icon = "\u2705" if is_ok else "\u274c"
    state = "OK" if is_ok else "DOWN"
    return f"{icon} {label} \u2014 {state}"


def _format_change_line(label: str, is_ok: bool, was_ok: bool) -> str:
    icon = "\u2705" if is_ok else "\u274c"
    if is_ok and not was_ok:
        return f"{icon} {label} \u2014 OK (was DOWN)"
    elif not is_ok and was_ok:
        return f"{icon} {label} \u2014 DOWN (was UP)"
    else:
        state = "OK" if is_ok else "DOWN"
        return f"{icon} {label} \u2014 {state}"


def format_summary(status: HealthStatus) -> str:
    all_ok = all(getattr(status, field) for field, _ in CHECK_LABELS)
    header = "\U0001f7e2 Minecraft Server Status" if all_ok else "\U0001f534 Minecraft Server Status"
    lines = [header, ""]
    for field, label in CHECK_LABELS:
        lines.append(_format_status_line(label, getattr(status, field)))
    lines.append("")
    lines.append(f"Last checked: {status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)


def format_alert(current: HealthStatus, previous: HealthStatus) -> str:
    lines = ["\U0001f6a8 Minecraft Server Alert", ""]
    for field, label in CHECK_LABELS:
        cur = getattr(current, field)
        prev = getattr(previous, field)
        lines.append(_format_change_line(label, cur, prev))
    return "\n".join(lines)


def run_healthcheck() -> None:
    """Main healthcheck function called every 5 minutes to detect state changes."""
    global _previous_status

    status = run_all_checks()

    logger.info(
        "Healthcheck: java_local=%s bedrock_local=%s playit=%s java_tunnel=%s bedrock_tunnel=%s",
        status.java_local,
        status.bedrock_local,
        status.playit_service,
        status.java_tunnel,
        status.bedrock_tunnel,
    )

    # Detect state changes and alert
    if _previous_status is not None:
        changed = any(
            getattr(status, field) != getattr(_previous_status, field)
            for field, _ in CHECK_LABELS
        )
        if changed:
            msg = format_alert(status, _previous_status)
            send_message_to_me(msg)

    _previous_status = status


def run_daily_summary() -> None:
    """Send a daily status summary."""
    status = run_all_checks()
    msg = format_summary(status)
    send_message_to_me(msg)


def run_on_demand_check() -> str:
    """Run checks and return a formatted summary (for on-demand button)."""
    status = run_all_checks()
    return format_summary(status)
