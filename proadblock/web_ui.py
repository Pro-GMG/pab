import logging
import ssl

from flask import Flask, jsonify, request, send_file

from . import blocklist, config, settings

logger = logging.getLogger(__name__)

DASHBOARD_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>ProAdBlock Yönetim Paneli</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/logo.png">
<style>
  :root {
    --bg: #0a0c0f; --panel: #15181d; --panel-2: #1c2028; --border: #262b33;
    --text: #f2f4f7; --muted: #8b95a1; --red: #e0262b; --red-glow: rgba(224,38,43,.35);
    --green: #2ecc71; --green-glow: rgba(46,204,113,.3);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background:
      radial-gradient(900px 420px at 15% -10%, rgba(224,38,43,.10), transparent 60%),
      radial-gradient(700px 360px at 100% 0%, rgba(46,204,113,.06), transparent 55%),
      var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  header {
    display: flex; align-items: center; gap: 14px;
    padding: 18px 28px; border-bottom: 1px solid var(--border);
    background: rgba(21, 24, 29, .7); backdrop-filter: blur(10px);
    position: sticky; top: 0; z-index: 10;
  }
  header img {
    width: 42px; height: 42px; border-radius: 11px;
    box-shadow: 0 0 0 1px var(--border), 0 6px 18px -6px var(--red-glow);
  }
  header h1 { font-size: 18px; margin: 0; letter-spacing: -.01em; }
  header .sub { color: var(--muted); font-size: 12.5px; margin-top: 1px; }
  header .spacer { flex: 1; }
  .toggle-wrap { display: flex; align-items: center; gap: 12px; }
  .toggle-label { font-size: 13px; color: var(--muted); font-weight: 600; transition: color .2s; }
  .toggle-label.on { color: var(--green); }
  .switch { position: relative; width: 50px; height: 28px; flex-shrink: 0; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider {
    position: absolute; cursor: pointer; inset: 0; background: #2a1616;
    border: 1px solid var(--border); border-radius: 999px; transition: .2s;
  }
  .slider::before {
    content: ""; position: absolute; height: 20px; width: 20px; left: 3px; top: 3px;
    background: white; border-radius: 50%; transition: .2s; box-shadow: 0 1px 3px rgba(0,0,0,.4);
  }
  input:checked + .slider { background: #12331f; box-shadow: 0 0 14px var(--green-glow) inset; }
  input:checked + .slider::before { transform: translateX(22px); }
  main { max-width: 960px; margin: 0 auto; padding: 28px 28px 48px; }
  .banner {
    display: none; align-items: center; gap: 10px; background: linear-gradient(135deg, #3a1414, #2a1010);
    border: 1px solid var(--red); color: #ffb3b3; border-radius: 12px;
    padding: 13px 16px; font-size: 13px; margin-bottom: 22px;
  }
  .banner.show { display: flex; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }
  .card {
    background: linear-gradient(160deg, var(--panel-2), var(--panel));
    border: 1px solid var(--border); border-radius: 16px;
    padding: 18px 20px; transition: transform .15s, border-color .15s;
  }
  .card:hover { transform: translateY(-2px); border-color: #3a4048; }
  .card .icon { font-size: 15px; opacity: .8; margin-bottom: 6px; }
  .card .value { font-size: 28px; font-weight: 800; letter-spacing: -.02em; }
  .card .label { color: var(--muted); font-size: 12.5px; margin-top: 4px; }
  .card.blocked .value { color: var(--red); text-shadow: 0 0 22px var(--red-glow); }
  .card.allowed .value { color: var(--green); text-shadow: 0 0 22px var(--green-glow); }
  section {
    background: linear-gradient(160deg, var(--panel-2), var(--panel));
    border: 1px solid var(--border); border-radius: 16px; padding: 22px; margin-bottom: 18px;
  }
  section h2 {
    font-size: 12.5px; margin: 0 0 16px; color: var(--muted); text-transform: uppercase;
    letter-spacing: .06em; display: flex; align-items: center; gap: 8px; font-weight: 700;
  }
  table { width: 100%; border-collapse: collapse; }
  tr:hover td { background: rgba(255,255,255,.02); }
  td { padding: 9px 6px; border-bottom: 1px solid var(--border); font-size: 13.5px; }
  tr:last-child td { border-bottom: none; }
  td.count { text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
  .actions { display: flex; gap: 10px; flex-wrap: wrap; }
  button, input, select {
    font-family: inherit; font-size: 13.5px; border-radius: 9px; border: 1px solid var(--border);
    background: var(--panel-2); color: var(--text); padding: 10px 14px; transition: filter .15s, transform .1s;
  }
  button { cursor: pointer; }
  button.primary {
    background: linear-gradient(135deg, var(--red), #a81b1f); border-color: var(--red);
    color: white; font-weight: 700; box-shadow: 0 4px 14px -4px var(--red-glow);
  }
  button.ghost { background: transparent; }
  button:hover { filter: brightness(1.15); }
  button:active { transform: scale(.97); }
  input:focus, select:focus { outline: none; border-color: #454c56; }
  .status { color: var(--muted); font-size: 12.5px; margin-top: 10px; min-height: 16px; }
  form.inline { display: flex; gap: 8px; }
  form.inline input { flex: 1; }
  .url-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 12.5px; }
  .url-row:last-child { border-bottom: none; }
  .url-row span { flex: 1; word-break: break-all; color: var(--text); }
  .preset-row { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
  .preset-row button.active {
    background: linear-gradient(135deg, var(--green), #1f9c58); border-color: var(--green);
    color: #04140a; font-weight: 700; box-shadow: 0 4px 14px -4px var(--green-glow);
  }
</style>
</head>
<body>
<header>
  <img src="/logo.png" alt="ProAdBlock">
  <div>
    <h1>ProAdBlock</h1>
    <div class="sub">DNS tabanlı reklam engelleme &mdash; yönetim paneli</div>
  </div>
  <div class="spacer"></div>
  <div class="toggle-wrap">
    <span class="toggle-label" id="toggle-label">Koruma: -</span>
    <label class="switch">
      <input type="checkbox" id="toggle-input" onchange="toggleProtection()">
      <span class="slider"></span>
    </label>
  </div>
</header>
<main>
  <div class="banner" id="paused-banner">⏸️ Koruma şu anda kapalı, reklamlar engellenmiyor.</div>
  <div class="cards">
    <div class="card blocked"><div class="icon">🚫</div><div class="value" id="v-blocked">-</div><div class="label">Engellenen istek</div></div>
    <div class="card allowed"><div class="icon">✅</div><div class="value" id="v-allowed">-</div><div class="label">İzin verilen istek</div></div>
    <div class="card"><div class="icon">📊</div><div class="value" id="v-ratio">-</div><div class="label">Engelleme oranı</div></div>
    <div class="card"><div class="icon">⏱️</div><div class="value" id="v-uptime">-</div><div class="label">Çalışma süresi</div></div>
  </div>

  <section>
    <h2>🏆 En çok engellenen domainler</h2>
    <table id="top-table"><tbody></tbody></table>
  </section>

  <section>
    <h2>🌐 Harici DNS (upstream)</h2>
    <div class="preset-row" id="preset-row"></div>
    <form class="inline" onsubmit="addCustomUpstream(event)">
      <input id="up-input" placeholder="Özel DNS IP ekle, örn. 94.140.14.14">
      <button class="primary" type="submit">Ekle</button>
    </form>
    <div id="custom-upstream-list"></div>
    <div class="status" id="upstream-status"></div>
  </section>

  <section>
    <h2>🧱 Reklam domain listeleri (blocklist)</h2>
    <div id="blocklist-urls"></div>
    <form class="inline" onsubmit="addBlocklistUrl(event)">
      <input id="bl-input" placeholder="https://.../blacklist" required>
      <button class="primary" type="submit">Ekle</button>
    </form>
    <div class="actions" style="margin-top:12px">
      <button class="primary" onclick="updateLists()">Listeleri şimdi güncelle</button>
    </div>
    <div class="status" id="update-status"></div>
  </section>

  <section>
    <h2>⚪ Beyaz listeye domain ekle</h2>
    <form class="inline" onsubmit="addWhitelist(event)">
      <input id="wl-input" placeholder="ornek.com" required>
      <button class="primary" type="submit">Ekle</button>
    </form>
    <div class="status" id="wl-status"></div>
  </section>
</main>
<script>
const PRESETS = [
  ['cloudflare', 'Cloudflare (1.1.1.1)'],
  ['google', 'Google (8.8.8.8)'],
  ['quad9', 'Quad9 (9.9.9.9)'],
  ['custom', 'Özel'],
];

function fmtUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}s ${m}dk` : `${m}dk`;
}

async function refreshStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('v-blocked').textContent = d.total_blocked.toLocaleString('tr-TR');
  document.getElementById('v-allowed').textContent = d.total_allowed.toLocaleString('tr-TR');
  document.getElementById('v-ratio').textContent = d.block_ratio + '%';
  document.getElementById('v-uptime').textContent = fmtUptime(d.uptime_seconds);
  const tbody = document.querySelector('#top-table tbody');
  tbody.innerHTML = '';
  if (d.top_blocked.length === 0) {
    tbody.innerHTML = '<tr><td colspan="2" style="color:var(--muted)">Henüz veri yok</td></tr>';
  }
  for (const [domain, count] of d.top_blocked) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${domain}</td><td class="count">${count}</td>`;
    tbody.appendChild(tr);
  }
}

let currentSettings = null;

async function refreshSettings() {
  const r = await fetch('/api/settings');
  currentSettings = await r.json();
  renderPresets();
  renderCustomUpstream();
  renderBlocklistUrls();
}

function renderPresets() {
  const row = document.getElementById('preset-row');
  row.innerHTML = '';
  for (const [key, label] of PRESETS) {
    const b = document.createElement('button');
    b.textContent = label;
    b.className = currentSettings.upstream_preset === key ? 'active' : 'ghost';
    b.onclick = () => setPreset(key);
    row.appendChild(b);
  }
}

function renderCustomUpstream() {
  const wrap = document.getElementById('custom-upstream-list');
  wrap.innerHTML = '';
  if (currentSettings.upstream_preset !== 'custom') return;
  for (const ip of currentSettings.upstream_custom) {
    const row = document.createElement('div');
    row.className = 'url-row';
    row.innerHTML = `<span>${ip}</span>`;
    const btn = document.createElement('button');
    btn.className = 'ghost'; btn.textContent = 'Kaldır';
    btn.onclick = () => removeCustomUpstream(ip);
    row.appendChild(btn);
    wrap.appendChild(row);
  }
}

function renderBlocklistUrls() {
  const wrap = document.getElementById('blocklist-urls');
  wrap.innerHTML = '';
  for (const url of currentSettings.blocklist_urls) {
    const row = document.createElement('div');
    row.className = 'url-row';
    row.innerHTML = `<span>${url}</span>`;
    const btn = document.createElement('button');
    btn.className = 'ghost'; btn.textContent = 'Kaldır';
    btn.onclick = () => removeBlocklistUrl(url);
    row.appendChild(btn);
    wrap.appendChild(row);
  }
}

async function saveSettings() {
  await fetch('/api/settings', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(currentSettings)
  });
}

async function setPreset(key) {
  currentSettings.upstream_preset = key;
  await saveSettings();
  await refreshSettings();
  document.getElementById('upstream-status').textContent = 'Harici DNS güncellendi.';
}

async function addCustomUpstream(e) {
  e.preventDefault();
  const input = document.getElementById('up-input');
  const ip = input.value.trim();
  if (!ip) return;
  currentSettings.upstream_preset = 'custom';
  currentSettings.upstream_custom.push(ip);
  await saveSettings();
  await refreshSettings();
  input.value = '';
}

async function removeCustomUpstream(ip) {
  currentSettings.upstream_custom = currentSettings.upstream_custom.filter(x => x !== ip);
  await saveSettings();
  await refreshSettings();
}

async function addBlocklistUrl(e) {
  e.preventDefault();
  const input = document.getElementById('bl-input');
  const url = input.value.trim();
  if (!url) return;
  currentSettings.blocklist_urls.push(url);
  await saveSettings();
  await refreshSettings();
  input.value = '';
}

async function removeBlocklistUrl(url) {
  currentSettings.blocklist_urls = currentSettings.blocklist_urls.filter(x => x !== url);
  await saveSettings();
  await refreshSettings();
}

async function updateLists() {
  const status = document.getElementById('update-status');
  status.textContent = 'Güncelleniyor...';
  const r = await fetch('/api/update', { method: 'POST' });
  const d = await r.json();
  status.textContent = `${d.count} domain yüklendi.`;
}

async function addWhitelist(e) {
  e.preventDefault();
  const input = document.getElementById('wl-input');
  const status = document.getElementById('wl-status');
  const r = await fetch('/api/whitelist', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ domain: input.value })
  });
  const d = await r.json();
  status.textContent = d.ok ? `${input.value} beyaz listeye eklendi.` : 'Hata oluştu.';
  input.value = '';
}

function applyStatus(enabled) {
  document.getElementById('toggle-input').checked = enabled;
  const label = document.getElementById('toggle-label');
  label.textContent = 'Koruma: ' + (enabled ? 'Açık' : 'Kapalı');
  label.classList.toggle('on', enabled);
  document.getElementById('paused-banner').classList.toggle('show', !enabled);
}

async function refreshStatus() {
  const r = await fetch('/api/status');
  const d = await r.json();
  applyStatus(d.enabled);
}

async function toggleProtection() {
  const checked = document.getElementById('toggle-input').checked;
  const r = await fetch('/api/toggle', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ enabled: checked })
  });
  const d = await r.json();
  applyStatus(d.enabled);
}

refreshStats();
refreshSettings();
refreshStatus();
setInterval(refreshStats, 3000);
</script>
</body>
</html>
"""


def create_app(matcher, stats, dns_server=None) -> Flask:
    app = Flask(__name__)
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    @app.get("/")
    def index():
        return DASHBOARD_HTML

    @app.get("/logo.png")
    def logo():
        return send_file(config.ICON_FILE, mimetype="image/png")

    @app.get("/api/stats")
    def api_stats():
        return jsonify(stats.snapshot())

    @app.get("/api/status")
    def api_status():
        return jsonify({"enabled": dns_server.enabled if dns_server else True})

    @app.post("/api/toggle")
    def api_toggle():
        if dns_server is None:
            return jsonify({"enabled": True})
        desired = (request.json or {}).get("enabled")
        new_state = bool(desired) if desired is not None else not dns_server.enabled
        dns_server.set_enabled(new_state)
        return jsonify({"enabled": dns_server.enabled})

    @app.get("/api/settings")
    def api_get_settings():
        return jsonify(settings.load())

    @app.post("/api/settings")
    def api_post_settings():
        data = request.json or {}
        current = settings.load()
        current["upstream_preset"] = data.get("upstream_preset", current["upstream_preset"])
        current["upstream_custom"] = data.get("upstream_custom", current["upstream_custom"])
        current["blocklist_urls"] = data.get("blocklist_urls", current["blocklist_urls"])
        settings.save(current)
        if dns_server is not None:
            dns_server.set_upstream(settings.resolve_upstream(current))
        return jsonify(current)

    @app.post("/api/update")
    def api_update():
        urls = settings.resolve_blocklist_urls()
        count = blocklist.update_blocklists(urls)
        matcher.update(blocklist.load_domains(), blocklist.load_whitelist())
        return jsonify({"count": count})

    @app.post("/api/whitelist")
    def api_whitelist():
        domain = (request.json or {}).get("domain", "").strip().lower()
        if not domain:
            return jsonify({"ok": False}), 400
        blocklist.add_to_whitelist(domain)
        matcher.update(blocklist.load_domains(), blocklist.load_whitelist())
        return jsonify({"ok": True})

    return app


def make_server(matcher, stats, host: str, port: int, dns_server=None, ssl_context=None):
    """Returns a werkzeug server bound to (host, port) that can be run in a thread
    and stopped cleanly via .shutdown(). Raises OSError if the port is unavailable."""
    from werkzeug.serving import make_server as _make_server

    app = create_app(matcher, stats, dns_server=dns_server)
    return _make_server(host, port, app, ssl_context=ssl_context)


def build_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    return ctx
