"""Opt-in playtest log (off by default).

Design §9.10 keeps raw player input out of the normal logs. For playtesting we
sometimes need it: set PLAYTEST_LOG=/path/to/file.jsonl and every turn appends
one JSON line with the input, the judge's answers, the rule that fired, the
fragment ids chosen and the text shown. Never enable this on the public
deployment without telling players.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("fly.playtest")
_lock = threading.Lock()


def playtest_path() -> str | None:
    return os.environ.get("PLAYTEST_LOG") or None


def write_playtest(record: dict[str, Any]) -> None:
    path = playtest_path()
    if not path:
        return
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **record}
    line = json.dumps(record, ensure_ascii=False, default=str)
    try:
        with _lock, open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:  # logging must never break a turn
        log.warning("playtest log write failed: %s", e)
