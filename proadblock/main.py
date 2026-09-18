import argparse
import ctypes
import logging
import os
import signal
import sys
import threading

from . import blocklist, config, instance, settings, system_dns, tls, tray, web_ui
from .dns_server import ProAdBlockDNSServer
from .matcher import DomainMatcher
from .stats import Stats

# Windows konsolunun varsayılan kod sayfası (cp1252) Türkçe karakterleri
# (ı, ş, ğ...) desteklemiyor ve print()/argparse çıktısında UnicodeEncodeError
# ile çökmeye sebep oluyor; çıktıyı UTF-8'e zorlayıp bunu önlüyoruz.
# --windowed (konsolsuz) derlemede stdout/stderr zaten None olabilir.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None:
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

HAS_CONSOLE = sys.stdout is not None


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers = []
    if HAS_CONSOLE:
        handlers.append(logging.StreamHandler(sys.stdout))
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    except OSError as exc:
        if HAS_CONSOLE:
            print(f"Uyarı: log dosyası açılamadı ({exc}), sadece konsola yazılacak.")

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _is_admin() -> bool:
    if sys.platform == "win32":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _start_web_servers(matcher, stats, dns_server):
    threads = []

    try:
        http_server = web_ui.make_server(matcher, stats, config.WEB_UI_HOST, config.WEB_UI_HTTP_PORT, dns_server=dns_server)
        http_port = config.WEB_UI_HTTP_PORT
    except OSError:
        http_server = web_ui.make_server(matcher, stats, config.WEB_UI_HOST, config.WEB_UI_HTTP_FALLBACK_PORT, dns_server=dns_server)
        http_port = config.WEB_UI_HTTP_FALLBACK_PORT
    threads.append(threading.Thread(target=http_server.serve_forever, daemon=True))

    https_server = None
    https_port = None
    try:
        cert_path, key_path = tls.ensure_self_signed_cert()
        ssl_ctx = web_ui.build_ssl_context(cert_path, key_path)
        try:
            https_server = web_ui.make_server(matcher, stats, config.WEB_UI_HOST, config.WEB_UI_HTTPS_PORT,
                                               dns_server=dns_server, ssl_context=ssl_ctx)
            https_port = config.WEB_UI_HTTPS_PORT
        except OSError:
            https_server = web_ui.make_server(matcher, stats, config.WEB_UI_HOST, config.WEB_UI_HTTPS_FALLBACK_PORT,
                                               dns_server=dns_server, ssl_context=ssl_ctx)
            https_port = config.WEB_UI_HTTPS_FALLBACK_PORT
        threads.append(threading.Thread(target=https_server.serve_forever, daemon=True))
    except Exception as exc:
        logging.getLogger(__name__).warning("HTTPS sunucusu başlatılamadı: %s", exc)

    for t in threads:
        t.start()

    return http_server, http_port, https_server, https_port


def _bootstrap(urls: list[str] | None, report) -> dict:
    """Core startup sequence shared by console `start` and the double-click GUI
    launch. `report(msg)` is called with short progress strings as we go."""
    if not _is_admin():
        raise RuntimeError("Bu işlem için yönetici/root yetkisi gerekiyor.")

    report("Önceki ProAdBlock oturumları kapatılıyor...")
    instance.kill_other_instances()

    report("Ayarlar yükleniyor...")
    user_settings = settings.load()
    urls = urls or settings.resolve_blocklist_urls(user_settings)

    has_cache = os.path.exists(os.path.join(config.CACHE_DIR, "merged.txt"))
    if has_cache:
        report("Önbellekteki blocklist kullanılıyor...")
    else:
        report("Blocklist indiriliyor (ilk çalıştırma)...")
        blocklist.update_blocklists(urls)

    stats = Stats()
    matcher = DomainMatcher(blocklist.load_domains(), blocklist.load_whitelist())
    dns_server = ProAdBlockDNSServer(
        config.LISTEN_HOST, config.LISTEN_PORT, matcher, stats=stats,
        upstream_servers=settings.resolve_upstream(user_settings),
    )

    report("Yönetim paneli başlatılıyor...")
    http_server, http_port, https_server, https_port = _start_web_servers(matcher, stats, dns_server)

    report("Sistem DNS ayarlanıyor...")
    system_dns.enable(config.LISTEN_HOST)

    dns_thread = threading.Thread(target=dns_server.run_forever, daemon=True)
    dns_thread.start()

    if has_cache:
        def _background_update():
            count = blocklist.update_blocklists(urls)
            matcher.update(blocklist.load_domains(), blocklist.load_whitelist())
            logging.getLogger(__name__).info("Blocklist güncellendi: %d domain.", count)

        threading.Thread(target=_background_update, daemon=True).start()

    _stopped = threading.Event()

    def shutdown():
        if _stopped.is_set():
            return
        _stopped.set()
        logging.getLogger(__name__).info("Durduruluyor, sistem DNS ayarları geri yükleniyor...")
        stats.save()
        system_dns.disable()
        dns_server.shutdown()
        http_server.shutdown()
        if https_server:
            https_server.shutdown()

    report("Hazır.")

    return {
        "dns_thread": dns_thread,
        "http_port": http_port,
        "https_port": https_port,
        "shutdown": shutdown,
    }


def cmd_start(args: argparse.Namespace) -> None:
    def report(msg: str):
        if HAS_CONSOLE:
            print(msg)
        logging.getLogger(__name__).info(msg)

    try:
        ctx = _bootstrap(args.urls, report)
    except RuntimeError as exc:
        report(str(exc))
        sys.exit(1)

    http_port, https_port = ctx["http_port"], ctx["https_port"]
    print(f"Yönetim paneli (her zaman çalışır): http://127.0.0.1:{http_port}/")
    domain_line = f"http://{config.ADMIN_DOMAIN}" + ("" if http_port == 80 else f":{http_port}") + "/"
    print(f"Yönetim paneli (kolay adres, tarayıcı/DNS ayarına bağlı): {domain_line}")
    if https_port:
        https_line = f"https://{config.ADMIN_DOMAIN}" + ("" if https_port == 443 else f":{https_port}") + "/"
        print(f"Yönetim paneli (TLS, kendinden imzalı sertifika): {https_line}")
    print(f"ProAdBlock çalışıyor ({config.LISTEN_HOST}:{config.LISTEN_PORT}).")

    def _signal_shutdown(*_):
        ctx["shutdown"]()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_shutdown)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _signal_shutdown)

    if args.no_tray:
        try:
            ctx["dns_thread"].join()
        except KeyboardInterrupt:
            ctx["shutdown"]()
    else:
        print("Sistem tepsisinden yönetim paneline erişebilirsiniz.")
        tray.run_tray(ctx["shutdown"], http_port)
        ctx["shutdown"]()


def _gui_start() -> None:
    """Double-click launch path: no console, an instant splash window while
    the DNS proxy / panel / tray come up in the background."""
    from .splash import Splash

    splash = Splash()
    result: dict = {}

    def worker():
        try:
            result["ctx"] = _bootstrap(None, splash.set_status)
            splash.finish(
                "ProAdBlock artık arka planda çalışıyor. Ayarları görmek için "
                "sağ alttaki (saat yanındaki gizli simgeler) ProAdBlock simgesine tıklayın."
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("Başlatma hatası")
            splash.fail(str(exc))

    threading.Thread(target=worker, daemon=True).start()
    try:
        splash.run_blocking()
    except Exception:
        # Tkinter/Tcl'in kendisi başlatılamazsa (ör. paketleme sorunu),
        # splash penceresi hiç açılamaz; kullanıcı hiç uyarı görmeden
        # sessizce kapanmasın diye tkinter'dan bağımsız native mesaj kutusu.
        logging.getLogger(__name__).exception("Splash başlatılamadı")
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(
                0,
                "ProAdBlock arayüzü başlatılamadı. Ayrıntılar için log dosyasına bakın:\n"
                f"{config.LOG_FILE}",
                "ProAdBlock - Hata", 0x10,
            )
        return

    ctx = result.get("ctx")
    if ctx is None:
        return

    signal.signal(signal.SIGINT, lambda *_: (ctx["shutdown"](), sys.exit(0)))
    tray.run_tray(ctx["shutdown"], ctx["http_port"])
    ctx["shutdown"]()


def cmd_stop(args: argparse.Namespace) -> None:
    if not _is_admin():
        print("Bu işlem için yönetici/root yetkisi gerekiyor.")
        sys.exit(1)
    system_dns.disable()
    print("Sistem DNS ayarları geri yüklendi.")


def cmd_update(args: argparse.Namespace) -> None:
    urls = args.urls or settings.resolve_blocklist_urls()
    count = blocklist.update_blocklists(urls)
    print(f"{count} domain güncellendi.")


def cmd_whitelist(args: argparse.Namespace) -> None:
    blocklist.add_to_whitelist(args.domain)
    print(f"{args.domain} beyaz listeye eklendi.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proadblock", description="DNS tabanlı reklam engelleyici")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="DNS proxy'yi, yönetim panelini ve tepsi simgesini başlat")
    p_start.add_argument("--urls", nargs="*", default=None, help="Ek/özel blocklist URL'leri")
    p_start.add_argument("--no-tray", action="store_true", help="Tepsi simgesi olmadan çalıştır (sunucu modu)")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Sistem DNS ayarlarını geri yükle")
    p_stop.set_defaults(func=cmd_stop)

    p_update = sub.add_parser("update", help="Blocklist'leri yeniden indir")
    p_update.add_argument("--urls", nargs="*", default=None)
    p_update.set_defaults(func=cmd_update)

    p_wl = sub.add_parser("whitelist", help="Domain'i beyaz listeye ekle")
    p_wl.add_argument("domain")
    p_wl.set_defaults(func=cmd_whitelist)

    return parser


def main() -> None:
    # Konsolsuz (--windowed) derlemede çift tıklayınca hiç argüman gelmez:
    # bu durumda argparse yerine dogrudan splash + tray akışına giriyoruz.
    if len(sys.argv) == 1 and not HAS_CONSOLE:
        _setup_logging(False)
        _gui_start()
        return

    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
