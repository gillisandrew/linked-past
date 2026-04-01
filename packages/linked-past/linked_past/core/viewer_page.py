"""Self-contained HTML/CSS/JS viewer page for the linked-past result feed."""

VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>linked-past viewer</title>
<style>
/* ── Reset & base ─────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:         #f5f5f5;
  --surface:    #ffffff;
  --border:     #e0e0e0;
  --text:       #1a1a1a;
  --muted:      #6b7280;
  --header-bg:  #1e293b;
  --header-fg:  #f1f5f9;
  --accent:     #3b82f6;

  /* dataset colours */
  --ds-dprr:     #3b82f6;
  --ds-pleiades: #22c55e;
  --ds-periodo:  #a855f7;
  --ds-nomisma:  #eab308;
  --ds-crro:     #f97316;
  --ds-ocre:     #ef4444;
  --ds-edh:      #06b6d4;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg:        #0f172a;
    --surface:   #1e293b;
    --border:    #334155;
    --text:      #f1f5f9;
    --muted:     #94a3b8;
    --header-bg: #0f172a;
    --header-fg: #f1f5f9;
  }
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ── Fixed header ─────────────────────────────────────────────────────── */
#header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: var(--header-bg);
  color: var(--header-fg);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  height: 48px;
}

#header h1 {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

#status-indicator {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}

#status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
  transition: background 0.3s;
}

#status-dot.connected    { background: #22c55e; }
#status-dot.connecting   { background: #eab308; }
#status-dot.disconnected { background: #ef4444; }

/* ── Feed container ───────────────────────────────────────────────────── */
#feed-container {
  margin-top: 48px;
  padding: 16px;
  max-width: 960px;
  width: 100%;
  margin-left: auto;
  margin-right: auto;
  padding-top: 64px;
}

/* ── Empty state ──────────────────────────────────────────────────────── */
#empty-state {
  text-align: center;
  padding: 64px 0;
  color: var(--muted);
  font-size: 15px;
}

/* ── Feed item ────────────────────────────────────────────────────────── */
.feed-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.feed-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.feed-header:hover {
  background: color-mix(in srgb, var(--surface) 90%, var(--text) 10%);
}

.feed-body {
  padding: 14px;
}

.feed-item.collapsed .feed-body {
  display: none;
}

.feed-item.collapsed .feed-header {
  border-bottom: none;
}

/* ── Badges ───────────────────────────────────────────────────────────── */
.tool-badge {
  display: inline-block;
  background: var(--accent);
  color: #fff;
  border-radius: 9999px;
  padding: 1px 9px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: lowercase;
  flex-shrink: 0;
}

.dataset-badge {
  display: inline-block;
  border-radius: 9999px;
  padding: 1px 9px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: lowercase;
  color: #fff;
  flex-shrink: 0;
}

.dataset-badge[data-ds="dprr"]     { background: var(--ds-dprr); }
.dataset-badge[data-ds="pleiades"] { background: var(--ds-pleiades); }
.dataset-badge[data-ds="periodo"]  { background: var(--ds-periodo); }
.dataset-badge[data-ds="nomisma"]  { background: var(--ds-nomisma); color: #1a1a1a; }
.dataset-badge[data-ds="crro"]     { background: var(--ds-crro); }
.dataset-badge[data-ds="ocre"]     { background: var(--ds-ocre); }
.dataset-badge[data-ds="edh"]      { background: var(--ds-edh); color: #1a1a1a; }

.timestamp {
  margin-left: auto;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}

.collapse-toggle {
  color: var(--muted);
  font-size: 11px;
  flex-shrink: 0;
}

.collapse-toggle::after {
  content: "collapse";
}

.feed-item.collapsed .collapse-toggle::after {
  content: "expand";
}

/* ── Entity card ──────────────────────────────────────────────────────── */
.entity-card {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  background: var(--surface);
}

.entity-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.entity-card .subtitle {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 12px;
  word-break: break-all;
}

.entity-card .props {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin-bottom: 12px;
}

.entity-card .props dt {
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.entity-card .props dd {
  font-size: 13px;
  word-break: break-word;
}

.entity-card .xrefs {
  margin-top: 12px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

/* ── Query table ──────────────────────────────────────────────────────── */
.query-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.query-table th {
  text-align: left;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--surface) 80%, var(--text) 20%);
  border-bottom: 2px solid var(--border);
  font-weight: 600;
  color: var(--text);
}

.query-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  word-break: break-word;
}

.query-table tr:hover td {
  background: color-mix(in srgb, var(--surface) 93%, var(--text) 7%);
}

.table-footer {
  font-size: 11px;
  color: var(--muted);
  margin-top: 6px;
  text-align: right;
}

/* ── Cross-reference list ─────────────────────────────────────────────── */
.xref-group {
  margin-bottom: 10px;
}

.xref-group-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin-bottom: 4px;
}

.xref-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.xref-item a {
  color: var(--accent);
  text-decoration: none;
  word-break: break-all;
}

.xref-item a:hover { text-decoration: underline; }

.confidence-badge {
  display: inline-block;
  border-radius: 9999px;
  padding: 1px 7px;
  font-size: 10px;
  font-weight: 600;
  text-transform: lowercase;
  flex-shrink: 0;
}

.confidence-badge.confirmed  { background: #22c55e; color: #fff; }
.confidence-badge.probable   { background: #eab308; color: #1a1a1a; }
.confidence-badge.candidate  { background: #94a3b8; color: #fff; }

/* ── Search results ───────────────────────────────────────────────────── */
.search-group {
  margin-bottom: 10px;
}

.search-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}

.search-item:last-child { border-bottom: none; }

.search-item .uri {
  font-size: 11px;
  color: var(--muted);
  word-break: break-all;
}

/* ── SPARQL query block ──────────────────────────────────────────────── */
.sparql-details { margin-bottom: 8px; }
.sparql-details summary {
  cursor: pointer; font-size: 12px; color: var(--muted);
  font-weight: 600; user-select: none;
}
.sparql-query {
  background: color-mix(in srgb, var(--surface) 85%, var(--text) 15%);
  border-radius: 4px; padding: 8px 12px; margin-top: 4px;
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 12px; white-space: pre-wrap; word-break: break-word;
  overflow-x: auto;
}

/* ── Generic result ───────────────────────────────────────────────────── */
.generic-result {
  background: color-mix(in srgb, var(--surface) 85%, var(--text) 15%);
  border-radius: 4px;
  padding: 12px;
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}
</style>
</head>
<body>

<div id="header">
  <h1>linked-past viewer</h1>
  <div id="status-indicator">
    <div id="status-dot" class="disconnected"></div>
    <span id="status-text">disconnected</span>
  </div>
</div>

<div id="feed-container">
  <div id="empty-state">Waiting for results&hellip;</div>
  <div id="feed"></div>
</div>

<script>
(function () {
  const feed        = document.getElementById('feed');
  const emptyState  = document.getElementById('empty-state');
  const statusDot   = document.getElementById('status-dot');
  const statusText  = document.getElementById('status-text');

  let ws        = null;
  let retryMs   = 1000;
  const MAX_MS  = 30000;

  function setStatus(state, label) {
    statusDot.className = state;
    statusText.textContent = label;
  }

  function collapseAll() {
    feed.querySelectorAll('.feed-item').forEach(function (el) {
      el.classList.add('collapsed');
    });
  }

  function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  }

  function onMessage(evt) {
    // Remove empty state on first result
    if (emptyState) {
      emptyState.remove();
    }

    // Collapse existing items
    collapseAll();

    // Append new fragment
    const tmp = document.createElement('div');
    tmp.innerHTML = evt.data;
    while (tmp.firstChild) {
      feed.appendChild(tmp.firstChild);
    }

    scrollToBottom();
  }

  // Event delegation for collapse toggle
  document.addEventListener('click', function (evt) {
    const header = evt.target.closest('.feed-header');
    if (!header) return;
    const item = header.closest('.feed-item');
    if (item) item.classList.toggle('collapsed');
  });

  function connect() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url   = proto + '//' + window.location.host + '/viewer/ws';

    setStatus('connecting', 'connecting…');
    ws = new WebSocket(url);

    ws.addEventListener('open', function () {
      setStatus('connected', 'connected');
      retryMs = 1000;
    });

    ws.addEventListener('message', onMessage);

    ws.addEventListener('close', function () {
      setStatus('disconnected', 'disconnected');
      ws = null;
      setTimeout(reconnect, retryMs);
      retryMs = Math.min(retryMs * 2, MAX_MS);
    });

    ws.addEventListener('error', function () {
      ws.close();
    });
  }

  function reconnect() {
    if (!ws) connect();
  }

  connect();
})();
</script>
</body>
</html>"""
