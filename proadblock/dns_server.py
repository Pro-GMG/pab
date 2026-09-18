import logging
import socket
import socketserver
import threading

from dnslib import QTYPE, RCODE, RR, A, AAAA, DNSRecord

from . import config
from .matcher import DomainMatcher

logger = logging.getLogger(__name__)

BLOCK_IPV4 = "0.0.0.0"


class _UpstreamPool:
    def __init__(self, servers: list[tuple[str, int]]):
        self._servers = servers

    def query(self, data: bytes, timeout: float = 3.0) -> bytes | None:
        for host, port in self._servers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                sock.sendto(data, (host, port))
                response, _ = sock.recvfrom(4096)
                sock.close()
                return response
            except (socket.timeout, OSError) as exc:
                logger.debug("Upstream %s:%d başarısız: %s", host, port, exc)
                continue
        return None


class _DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        server: ProAdBlockDNSServer = self.server

        try:
            request = DNSRecord.parse(data)
        except Exception:
            return

        qname = str(request.q.qname)
        qtype = QTYPE[request.q.qtype]
        host = qname.rstrip(".").lower()

        if host == server.admin_domain or host.endswith("." + server.admin_domain):
            reply = request.reply()
            if qtype == "A":
                reply.add_answer(RR(qname, QTYPE.A, rdata=A("127.0.0.1"), ttl=60))
            sock.sendto(reply.pack(), self.client_address)
            return

        if server.enabled and server.matcher.is_blocked(qname):
            reply = request.reply()
            if qtype == "A":
                reply.add_answer(RR(qname, QTYPE.A, rdata=A(BLOCK_IPV4), ttl=60))
            elif qtype == "AAAA":
                pass
            else:
                reply.header.rcode = RCODE.NXDOMAIN
            server.on_block(qname)
            sock.sendto(reply.pack(), self.client_address)
            return

        response = server.upstream.query(data)
        if response is None:
            reply = request.reply()
            reply.header.rcode = RCODE.SERVFAIL
            sock.sendto(reply.pack(), self.client_address)
            return

        server.on_allow(qname)
        sock.sendto(response, self.client_address)


class ProAdBlockDNSServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, host: str, port: int, matcher: DomainMatcher,
                 upstream_servers: list[tuple[str, int]] | None = None,
                 stats=None, admin_domain: str = config.ADMIN_DOMAIN):
        super().__init__((host, port), _DNSHandler)
        self.matcher = matcher
        self.upstream = _UpstreamPool(upstream_servers or config.DEFAULT_UPSTREAM_DNS)
        self.stats = stats
        self.admin_domain = admin_domain.lower()
        self.enabled = True
        self._lock = threading.Lock()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def on_block(self, qname: str) -> None:
        if self.stats:
            self.stats.record_block(qname.rstrip(".").lower())
        logger.debug("BLOCKED %s", qname)

    def on_allow(self, qname: str) -> None:
        if self.stats:
            self.stats.record_allow(qname.rstrip(".").lower())

    def set_upstream(self, servers: list[tuple[str, int]]) -> None:
        self.upstream = _UpstreamPool(servers)

    def run_forever(self) -> None:
        logger.info("DNS proxy dinliyor: %s:%d", *self.server_address)
        self.serve_forever()
