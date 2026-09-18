import hashlib
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from . import config

logger = logging.getLogger(__name__)

_HOSTS_LINE_RE = re.compile(r"^\s*(0\.0\.0\.0|127\.0\.0\.1)\s+([a-zA-Z0-9_.\-]+)")
_PLAIN_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

IGNORED_DOMAINS = {"localhost", "localhost.localdomain", "local", "broadcasthost", "ip6-localhost", "ip6-loopback"}


def _cache_path_for(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return os.path.join(config.CACHE_DIR, f"{digest}.txt")


def _parse_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("!"):
        return None

    m = _HOSTS_LINE_RE.match(line)
    if m:
        domain = m.group(2).lower()
    elif _PLAIN_DOMAIN_RE.match(line):
        domain = line.lower()
    else:
        return None

    if domain in IGNORED_DOMAINS:
        return None
    return domain


def _fetch_url(url: str, timeout: int = 10) -> str | None:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ProAdBlock/1.0"})
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.warning("Blocklist indirilemedi (%s): %s", url, exc)
        return None


def _fetch_or_cached(url: str) -> str | None:
    text = _fetch_url(url)
    cache_path = _cache_path_for(url)

    if text is None:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                text = f.read()
            logger.info("Önbellekten okunuyor: %s", url)
        return text

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def update_blocklists(urls: list[str] | None = None) -> int:
    """Downloads all configured blocklists in parallel and merges them. Returns total unique domain count."""
    urls = urls or config.DEFAULT_BLOCKLIST_URLS
    domains: set[str] = set()

    with ThreadPoolExecutor(max_workers=max(1, len(urls))) as pool:
        futures = {pool.submit(_fetch_or_cached, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            text = future.result()
            if text is None:
                continue

            count_before = len(domains)
            for line in text.splitlines():
                domain = _parse_line(line)
                if domain:
                    domains.add(domain)
            logger.info("%s -> %d domain eklendi", url, len(domains) - count_before)

    merged_path = os.path.join(config.CACHE_DIR, "merged.txt")
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(domains)))

    return len(domains)


def load_domains() -> set[str]:
    merged_path = os.path.join(config.CACHE_DIR, "merged.txt")
    if not os.path.exists(merged_path):
        update_blocklists()

    with open(merged_path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def load_whitelist() -> set[str]:
    whitelist_path = os.path.join(config.CACHE_DIR, "whitelist.txt")
    if not os.path.exists(whitelist_path):
        return set()
    with open(whitelist_path, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip() and not line.startswith("#")}


def add_to_whitelist(domain: str) -> None:
    whitelist_path = os.path.join(config.CACHE_DIR, "whitelist.txt")
    existing = load_whitelist()
    existing.add(domain.lower().strip())
    with open(whitelist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(existing)))
