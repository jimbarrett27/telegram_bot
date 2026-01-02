from telegram_bot.telegram_bot import send_message_to_me
import re
import subprocess
import threading
import queue

PLAYER_JOINED_REGEX = re.compile(r"joined the game", re.IGNORECASE)
TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

LOG_QUEUE = None


def get_log_queue() -> queue.Queue[str]:
    global LOG_QUEUE
    if LOG_QUEUE is None:
        LOG_QUEUE = follow_journal("minecraft.service")
    return LOG_QUEUE

def follow_journal(unit: str) -> queue.Queue[str]:
    q: queue.Queue[str] = queue.Queue()

    def _reader():
        p = subprocess.Popen(
            ["journalctl", "-u", unit, "-f", "-o", "cat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert p.stdout is not None
        for line in p.stdout:
            q.put(line.rstrip("\n"))

    threading.Thread(target=_reader, daemon=True).start()
    return q


def react_to_logs():
    queue = get_log_queue()
    while not queue.empty():
        line = queue.get() 
        if PLAYER_JOINED_REGEX.search(line):
            send_message_to_me(line)
        
