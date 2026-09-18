import json
import os
import threading
import time
from collections import Counter

from . import config


class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self.total_blocked = 0
        self.total_allowed = 0
        self.since = time.time()
        self.top_blocked = Counter()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(config.STATS_FILE):
            return
        try:
            with open(config.STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.total_blocked = data.get("total_blocked", 0)
            self.total_allowed = data.get("total_allowed", 0)
            self.top_blocked = Counter(data.get("top_blocked", {}))
        except (json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        with self._lock:
            data = {
                "total_blocked": self.total_blocked,
                "total_allowed": self.total_allowed,
                "top_blocked": dict(self.top_blocked.most_common(200)),
            }
        with open(config.STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def record_block(self, domain: str) -> None:
        with self._lock:
            self.total_blocked += 1
            self.top_blocked[domain] += 1

    def record_allow(self, domain: str) -> None:
        with self._lock:
            self.total_allowed += 1

    def snapshot(self) -> dict:
        with self._lock:
            uptime = int(time.time() - self.since)
            total = self.total_blocked + self.total_allowed
            ratio = (self.total_blocked / total * 100) if total else 0.0
            return {
                "total_blocked": self.total_blocked,
                "total_allowed": self.total_allowed,
                "block_ratio": round(ratio, 1),
                "uptime_seconds": uptime,
                "top_blocked": self.top_blocked.most_common(10),
            }
