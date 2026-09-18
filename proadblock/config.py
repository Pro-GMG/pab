import os
import sys

APP_NAME = "ProAdBlock"

if sys.platform == "win32":
    DATA_DIR = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), APP_NAME)
else:
    DATA_DIR = os.path.join("/var/lib", APP_NAME.lower())
    if not os.access("/var/lib", os.W_OK):
        DATA_DIR = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")

CACHE_DIR = os.path.join(DATA_DIR, "cache")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LOG_FILE = os.path.join(DATA_DIR, "proadblock.log")

DEFAULT_BLOCKLIST_URLS = [
    "https://raw.githubusercontent.com/Pro-GMG/ProAdBlocker-Domain-Blacklist/refs/heads/main/blacklist",
    "https://raw.githubusercontent.com/StevenBlack/hosts/refs/heads/master/hosts",
]

DEFAULT_UPSTREAM_DNS = [
    ("1.1.1.1", 53),
    ("8.8.8.8", 53),
]

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 53

BLOCKLIST_REFRESH_SECONDS = 6 * 60 * 60  # 6 hours

ADMIN_DOMAIN = "ad.blocker.pro"
WEB_UI_HOST = "127.0.0.1"
WEB_UI_HTTP_PORT = 80
WEB_UI_HTTP_FALLBACK_PORT = 9000
WEB_UI_HTTPS_PORT = 443
WEB_UI_HTTPS_FALLBACK_PORT = 9443
TLS_CERT_FILE = os.path.join(DATA_DIR, "tls_cert.pem")
TLS_KEY_FILE = os.path.join(DATA_DIR, "tls_key.pem")

STATS_FILE = os.path.join(DATA_DIR, "stats.json")

if getattr(sys, "frozen", False):
    _BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_FILE = os.path.join(_BASE_DIR, "image.png")

os.makedirs(CACHE_DIR, exist_ok=True)
