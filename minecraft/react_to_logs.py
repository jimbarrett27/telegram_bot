from systemd import journal
import re

PLAYER_JOINED_REGEX = re.compile(r"^Player \[\w+\] joined the game$", re.IGNORECASE)

LOG_GENERATOR = None

def log_gen():
    
    j = journal.Reader()
    j.add_match(_SYSTEMD_UNIT="minecraft.service")
    j.seek_tail()
    j.get_previous()
    
    for entry in j:
        yield entry

def get_log_generator():
    global LOG_GENERATOR
    if LOG_GENERATOR is None:
        LOG_GENERATOR = log_gen()
    return LOG_GENERATOR

def react_to_logs():
    for log in get_log_generator():
        if PLAYER_JOINED_REGEX.match(log['MESSAGE']):
            send_message_to_me(log['MESSAGE'])
