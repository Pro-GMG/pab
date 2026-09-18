class DomainMatcher:
    """Fast domain + subdomain matcher backed by blocklist/whitelist domain sets."""

    def __init__(self, blocked: set[str], allowed: set[str] | None = None):
        self._blocked = blocked
        self._allowed = allowed or set()

    def update(self, blocked: set[str], allowed: set[str] | None = None) -> None:
        self._blocked = blocked
        self._allowed = allowed or set()

    def _labels_match(self, host: str, domains: set[str]) -> bool:
        parts = host.split(".")
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate in domains:
                return True
        return False

    def is_blocked(self, host: str) -> bool:
        host = host.rstrip(".").lower()
        if not host:
            return False
        if self._labels_match(host, self._allowed):
            return False
        return self._labels_match(host, self._blocked)
