"""
Session Awareness — ICT Killzones
Only trade during high-probability time windows.
"""

from datetime import datetime, timezone


# ICT killzone windows (UTC)
KILLZONES = {
    "ASIAN":   ((0, 0), (3, 0)),
    "LONDON":  ((7, 0), (10, 0)),
    "NY_AM":   ((13, 0), (16, 0)),
    "NY_PM":   ((17, 0), (19, 0)),
}

# Sessions valid for each direction tendency
VALID_SESSIONS = {"LONDON", "NY_AM"}  # Most liquidity here


def current_session():
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute

    for name, ((sh, sm), (eh, em)) in KILLZONES.items():
        start = sh * 60 + sm
        end = eh * 60 + em
        current = h * 60 + m
        if start <= current < end:
            return name

    return "OFF_HOURS"


def is_valid_session(strict=True):
    """
    strict=True  → only London and NY AM
    strict=False → allow all named sessions (not dead hours)
    """
    session = current_session()
    if strict:
        return session in VALID_SESSIONS
    return session != "OFF_HOURS"
