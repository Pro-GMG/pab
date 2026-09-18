import json
import logging
import os
import subprocess
import sys

from . import config

logger = logging.getLogger(__name__)


_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, creationflags=_NO_WINDOW)


def _save_state(state: dict) -> None:
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _load_state() -> dict:
    if not os.path.exists(config.STATE_FILE):
        return {}
    with open(config.STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- Windows --

def _windows_active_interfaces() -> list[str]:
    result = _run(["netsh", "interface", "show", "interface"])
    names = []
    for line in result.stdout.splitlines():
        if "Connected" in line and "Dedicated" in line:
            parts = line.split(None, 3)
            if len(parts) == 4:
                names.append(parts[3].strip())
    return names


def _windows_current_dns(iface: str) -> list[str]:
    result = _run(["netsh", "interface", "ip", "show", "dns", iface])
    servers = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and line.count(".") == 3:
            servers.append(line.split()[0])
    return servers


def _windows_set_dns(iface: str, dns_ip: str) -> None:
    _run(["netsh", "interface", "ip", "set", "dns", f'name={iface}', "static", dns_ip, "primary"])


def _windows_restore_dns(iface: str) -> None:
    _run(["netsh", "interface", "ip", "set", "dns", f'name={iface}', "dhcp"])


def enable(dns_ip: str = config.LISTEN_HOST) -> None:
    if sys.platform == "win32":
        from concurrent.futures import ThreadPoolExecutor

        interfaces = _windows_active_interfaces()
        if not interfaces:
            raise RuntimeError("Aktif ağ arayüzü bulunamadı")
        with ThreadPoolExecutor(max_workers=max(1, len(interfaces))) as pool:
            previous = dict(zip(interfaces, pool.map(_windows_current_dns, interfaces)))
            list(pool.map(lambda i: _windows_set_dns(i, dns_ip), interfaces))
        _save_state({"platform": "windows", "interfaces": previous})

    elif sys.platform == "darwin":
        result = _run(["networksetup", "-listallnetworkservices"])
        services = [s for s in result.stdout.splitlines()[1:] if s and not s.startswith("*")]
        previous = {}
        for svc in services:
            cur = _run(["networksetup", "-getdnsservers", svc])
            previous[svc] = [] if "aren't" in cur.stdout.lower() else cur.stdout.split()
            _run(["networksetup", "-setdnsservers", svc, dns_ip])
        _save_state({"platform": "darwin", "services": previous})

    else:
        original = None
        if os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf", "r", encoding="utf-8") as f:
                original = f.read()
        with open("/etc/resolv.conf", "w", encoding="utf-8") as f:
            f.write(f"nameserver {dns_ip}\n")
        _save_state({"platform": "linux", "resolv_conf": original})

    logger.info("Sistem DNS'i %s olarak ayarlandı", dns_ip)


def disable() -> None:
    state = _load_state()
    if not state:
        logger.warning("Kayıtlı DNS durumu bulunamadı, geri alınamıyor")
        return

    plat = state.get("platform")

    if plat == "windows":
        for iface, servers in state.get("interfaces", {}).items():
            if servers:
                _windows_set_dns(iface, servers[0])
                for extra in servers[1:]:
                    _run(["netsh", "interface", "ip", "add", "dns", f'name={iface}', extra, "index=2"])
            else:
                _windows_restore_dns(iface)

    elif plat == "darwin":
        for svc, servers in state.get("services", {}).items():
            if servers:
                _run(["networksetup", "-setdnsservers", svc] + servers)
            else:
                _run(["networksetup", "-setdnsservers", svc, "Empty"])

    elif plat == "linux":
        original = state.get("resolv_conf")
        if original is not None:
            with open("/etc/resolv.conf", "w", encoding="utf-8") as f:
                f.write(original)

    if os.path.exists(config.STATE_FILE):
        os.remove(config.STATE_FILE)

    logger.info("Sistem DNS ayarları geri yüklendi")
