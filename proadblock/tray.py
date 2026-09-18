import logging
import threading
import webbrowser

from PIL import Image
import pystray

from . import config

logger = logging.getLogger(__name__)


def _open_panel(web_port: int) -> None:
    # 127.0.0.1 üzerinden aç: tarayıcı/OS DNS önbelleği, Secure DNS ya da
    # üçüncü parti bir DNS override'ının (VPN, Tailscale vb.) araya girip
    # ADMIN_DOMAIN'i yanlış çözmesi ihtimalini tamamen devre dışı bırakır.
    webbrowser.open(f"http://127.0.0.1:{web_port}/")


def run_tray(on_quit, web_port: int) -> None:
    """Blocks the calling (main) thread running the tray icon event loop."""
    try:
        image = Image.open(config.ICON_FILE)
    except (FileNotFoundError, OSError):
        image = Image.new("RGB", (64, 64), "red")

    def _quit(icon, item):
        icon.stop()
        on_quit()

    def _open(icon, item):
        _open_panel(web_port)

    menu = pystray.Menu(
        pystray.MenuItem("Yönetim Panelini Aç", _open, default=True),
        pystray.MenuItem("Çıkış", _quit),
    )
    icon = pystray.Icon("ProAdBlock", image, "ProAdBlock", menu)
    icon.run()
