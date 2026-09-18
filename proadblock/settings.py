import json
import os
import threading

from . import config

UPSTREAM_PRESETS = {
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "google": ["8.8.8.8", "8.8.4.4"],
    "quad9": ["9.9.9.9", "149.112.112.112"],
}

_DEFAULTS = {
    "upstream_preset": "cloudflare",
    "upstream_custom": [],
    "blocklist_urls": list(config.DEFAULT_BLOCKLIST_URLS),
}

_lock = threading.Lock()


def _settings_path() -> str:
    return os.path.join(config.DATA_DIR, "settings.json")


def load() -> dict:
    path = _settings_path()
    data = dict(_DEFAULTS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save(data: dict) -> None:
    with _lock:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def resolve_upstream(data: dict | None = None) -> list[tuple[str, int]]:
    data = data or load()
    if data.get("upstream_preset") == "custom" and data.get("upstream_custom"):
        ips = data["upstream_custom"]
    else:
        ips = UPSTREAM_PRESETS.get(data.get("upstream_preset"), UPSTREAM_PRESETS["cloudflare"])
    return [(ip, 53) for ip in ips]


def resolve_blocklist_urls(data: dict | None = None) -> list[str]:
    data = data or load()
    urls = data.get("blocklist_urls") or []
    return urls if urls else list(config.DEFAULT_BLOCKLIST_URLS)
