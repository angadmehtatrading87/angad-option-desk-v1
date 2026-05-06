"""
Live IG-clone dashboard.

Mounts at:
    GET  /live              → the HTML page (single-file, dark theme)
    GET  /live/state.json   → JSON state feed the page polls every 5s

The HTML is intentionally self-contained (one file, CDN-loaded Chart.js +
no server-side templating) so we can iterate fast without adding a build
step. Phase 3b will move the markup into proper templates.

Wired into FastAPI by appending `app.include_router(live_dashboard.router)`
in app/main.py.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.ui.state_aggregator import aggregate_live_state

router = APIRouter()


@router.get("/live/state.json")
def live_state_json():
    """JSON feed polled by the dashboard every 5s."""
    return JSONResponse(aggregate_live_state())


@router.get("/live", response_class=HTMLResponse)
def live_dashboard():
    """The single-file dashboard."""
    return HTMLResponse(_HTML)


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>Autobot Trader Pro — Live</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg-0: #0a0e1a;
      --bg-1: #0f1422;
      --bg-2: #161c2e;
      --bg-3: #1d2538;
      --line: #232c44;
      --text-0: #eef1f8;
      --text-1: #9ba8c1;
      --text-2: #6b7689;
      --good: #4ade80;
      --bad: #f87171;
      --warn: #fbbf24;
      --accent: #60a5fa;
      --accent-2: #a78bfa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg-0);
      color: var(--text-0);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "SF Pro Display", system-ui, sans-serif;
      font-size: 13px;
      line-height: 1.45;
      -webkit-font-smoothing: antialiased;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 24px;
      background: linear-gradient(180deg, var(--bg-1) 0%, var(--bg-0) 100%);
      border-bottom: 1px solid var(--line);
      position: sticky; top: 0; z-index: 10;
    }
    .topbar h1 {
      margin: 0; font-size: 16px; font-weight: 700;
      letter-spacing: -0.01em;
    }
    .topbar .sub { color: var(--text-2); font-size: 11px; margin-top: 2px; }
    .topbar .right { display: flex; gap: 16px; align-items: center; font-size: 12px; }
    .pill {
      display: inline-block; padding: 4px 10px; border-radius: 999px;
      font-size: 11px; font-weight: 600; letter-spacing: 0.02em;
      background: var(--bg-2); border: 1px solid var(--line); color: var(--text-1);
    }
    .pill.good { color: var(--good); border-color: rgba(74,222,128,0.25); background: rgba(74,222,128,0.06); }
    .pill.bad  { color: var(--bad);  border-color: rgba(248,113,113,0.25); background: rgba(248,113,113,0.06); }
    .pill.warn { color: var(--warn); border-color: rgba(251,191,36,0.25); background: rgba(251,191,36,0.06); }
    .container { padding: 18px 24px 60px; max-width: 1600px; margin: 0 auto; }
    .grid-stats {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
      margin-bottom: 16px;
    }
    .card {
      background: var(--bg-1);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px 16px;
    }
    .card .label {
      font-size: 11px;
      color: var(--text-2);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }
    .card .value {
      font-size: 22px; font-weight: 700; letter-spacing: -0.01em;
      font-variant-numeric: tabular-nums;
    }
    .card .sub {
      font-size: 11px; color: var(--text-1); margin-top: 4px;
    }
    .card .value.good { color: var(--good); }
    .card .value.bad  { color: var(--bad); }
    .grid-2 {
      display: grid; grid-template-columns: 2fr 1fr; gap: 14px;
      margin-bottom: 16px;
    }
    .panel {
      background: var(--bg-1);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px 18px;
    }
    .panel h2 {
      margin: 0 0 12px 0; font-size: 13px; font-weight: 600;
      color: var(--text-1);
      text-transform: uppercase; letter-spacing: 0.06em;
    }
    table {
      width: 100%; border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    th, td {
      padding: 8px 10px; text-align: left;
      border-bottom: 1px solid var(--line);
    }
    th {
      font-size: 10px; color: var(--text-2);
      text-transform: uppercase; letter-spacing: 0.05em;
      font-weight: 600;
    }
    td { font-size: 12px; }
    tr:last-child td { border-bottom: none; }
    .num { text-align: right; }
    .dir-long  { color: var(--good); font-weight: 700; }
    .dir-short { color: var(--bad);  font-weight: 700; }
    .dir-flat  { color: var(--text-2); }
    .score-bar {
      display: inline-block; height: 6px; border-radius: 3px;
      background: var(--bg-3); overflow: hidden; width: 80px;
      vertical-align: middle; margin-right: 6px;
    }
    .score-bar > i {
      display: block; height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }
    .progress {
      width: 100%; height: 5px; background: var(--bg-3);
      border-radius: 3px; overflow: hidden; margin-top: 4px;
    }
    .progress > i {
      display: block; height: 100%;
      background: linear-gradient(90deg, var(--good), var(--warn));
    }
    .progress.bad > i { background: linear-gradient(90deg, var(--warn), var(--bad)); }
    .grid-3 {
      display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px;
    }
    .footer {
      margin-top: 24px; color: var(--text-2);
      text-align: center; font-size: 11px;
    }
    .blink-dot {
      display: inline-block; width: 8px; height: 8px; border-radius: 50%;
      background: var(--good); margin-right: 6px; vertical-align: middle;
      box-shadow: 0 0 8px rgba(74,222,128,0.6);
      animation: blink 1.6s ease-in-out infinite;
    }
    @keyframes blink {
      0%,100% { opacity: 1; }
      50% { opacity: 0.35; }
    }
    canvas { max-width: 100%; height: 200px !important; }
    .errors {
      background: rgba(248,113,113,0.05);
      border: 1px solid rgba(248,113,113,0.25);
      color: var(--bad); padding: 8px 12px; border-radius: 8px;
      font-size: 11px; margin-bottom: 12px;
    }
    .empty { color: var(--text-2); font-style: italic; padding: 12px 0; font-size: 12px; }
    @media (max-width: 1100px) {
      .grid-stats { grid-template-columns: repeat(2, 1fr); }
      .grid-2     { grid-template-columns: 1fr; }
      .grid-3     { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Autobot Trader Pro <span style="font-weight:400;color:var(--text-2);">— IG demo</span></h1>
    <div class="sub" id="topbar-sub">connecting…</div>
  </div>
  <div class="right">
    <span class="pill" id="session-pill">—</span>
    <span class="pill" id="kill-pill">—</span>
    <span class="pill" id="trader-pill"><span class="blink-dot"></span>live</span>
  </div>
</div>

<div class="container">

  <div id="errors-box"></div>

  <div class="grid-stats">
    <div class="card">
      <div class="label">Equity</div>
      <div class="value" id="stat-equity">—</div>
      <div class="sub" id="stat-equity-sub">balance + open P&L</div>
    </div>
    <div class="card">
      <div class="label">Open P&amp;L</div>
      <div class="value" id="stat-openpnl">—</div>
      <div class="sub" id="stat-openpnl-sub">across all positions</div>
    </div>
    <div class="card">
      <div class="label">Available</div>
      <div class="value" id="stat-avail">—</div>
      <div class="sub" id="stat-avail-sub">free margin</div>
    </div>
    <div class="card">
      <div class="label">Open positions</div>
      <div class="value" id="stat-positions">—</div>
      <div class="sub" id="stat-positions-sub">live count</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2>Live decisions per pair</h2>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Direction</th>
            <th class="num">Score</th>
            <th class="num">Confidence</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="decisions-tbody">
          <tr><td colspan="5" class="empty">loading…</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Regime</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;font-size:12px;">
        <div style="color:var(--text-2);">Regime</div><div id="regime-name" style="font-weight:600;">—</div>
        <div style="color:var(--text-2);">Quality</div><div id="regime-quality">—</div>
        <div style="color:var(--text-2);">Deployment</div><div id="deployment-mode">—</div>
        <div style="color:var(--text-2);">Target deploy</div><div id="deployment-target">—</div>
        <div style="color:var(--text-2);">Floor</div><div id="deployment-floor">—</div>
        <div style="color:var(--text-2);">Book size</div><div id="book-size">—</div>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2>Open positions</h2>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Side</th><th class="num">Size</th><th class="num">Entry</th><th class="num">Current P&amp;L</th></tr>
        </thead>
        <tbody id="positions-tbody">
          <tr><td colspan="5" class="empty">none right now</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Multi-timeframe data</h2>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Mode</th><th>Sources</th></tr>
        </thead>
        <tbody id="mtf-tbody">
          <tr><td colspan="3" class="empty">loading…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="grid-3">
    <div class="panel">
      <h2>Cost cap usage today</h2>
      <div id="costcap-rows"></div>
    </div>
    <div class="panel">
      <h2>Shadow signals (24h)</h2>
      <div id="shadow-rows"></div>
    </div>
    <div class="panel">
      <h2>Score distribution</h2>
      <canvas id="score-chart"></canvas>
    </div>
  </div>

  <div class="footer">
    auto-refresh every 5s · last update <span id="last-update">—</span>
  </div>
</div>

<script>
const fmtMoney = v => (v == null) ? "—" : ("$" + Number(v).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0}));
const fmtMoney2 = v => (v == null) ? "—" : ("$" + Number(v).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}));
const fmtPct = v => (v == null) ? "—" : (Number(v).toFixed(0) + "%");
const fmtNum = (v, d=1) => (v == null) ? "—" : Number(v).toFixed(d);

let scoreChart = null;

async function tick() {
  try {
    const r = await fetch("/live/state.json", {cache: "no-store"});
    const s = await r.json();
    render(s);
    document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById("topbar-sub").textContent = "fetch error: " + e.message;
  }
}

function render(s) {
  // top bar
  document.getElementById("topbar-sub").textContent = s.ts + " — " + s.session;
  document.getElementById("session-pill").textContent = "session: " + s.session;

  const ks = s.kill_switches || {};
  const killEl = document.getElementById("kill-pill");
  if (ks.trading_killed) {
    killEl.textContent = "TRADING KILLED";
    killEl.className = "pill bad";
  } else if (ks.llm_calls_killed) {
    killEl.textContent = "LLM killed";
    killEl.className = "pill warn";
  } else {
    killEl.textContent = "all systems normal";
    killEl.className = "pill good";
  }

  // errors
  const errsBox = document.getElementById("errors-box");
  if (s.errors && s.errors.length) {
    errsBox.innerHTML = '<div class="errors">⚠ ' + s.errors.join(" · ") + '</div>';
  } else {
    errsBox.innerHTML = "";
  }

  // stats
  const acct = s.account || {};
  document.getElementById("stat-equity").textContent = fmtMoney(acct.equity);
  document.getElementById("stat-openpnl").textContent = fmtMoney2(acct.open_pnl);
  const opnl = acct.open_pnl;
  document.getElementById("stat-openpnl").className = "value " + (opnl > 0 ? "good" : (opnl < 0 ? "bad" : ""));
  document.getElementById("stat-avail").textContent = fmtMoney(acct.available);
  document.getElementById("stat-positions").textContent = (s.positions || []).length;

  // regime / deployment panel
  const r = s.regime || {};
  const dep = s.deployment || {};
  const book = s.book_directive || {};
  document.getElementById("regime-name").textContent = r.regime || "—";
  document.getElementById("regime-quality").textContent = fmtNum(r.quality_score, 0);
  document.getElementById("deployment-mode").textContent = dep.mode || "—";
  document.getElementById("deployment-target").textContent = (dep.target_pct == null) ? "—" : (dep.target_pct + "%");
  document.getElementById("deployment-floor").textContent = (dep.floor_pct == null) ? "—" : (dep.floor_pct + "%");
  document.getElementById("book-size").textContent = book.target_position_count || "—";

  // decisions table — built from `ranked` so we always show all 5 pairs,
  // not just the candidates that passed threshold
  const ranked = s.ranked || [];
  const candidateBySym = {};
  for (const c of (s.candidates || [])) candidateBySym[c.symbol] = c;
  const decisionsTbody = document.getElementById("decisions-tbody");
  if (ranked.length === 0) {
    decisionsTbody.innerHTML = '<tr><td colspan="5" class="empty">no scored pairs in current cycle</td></tr>';
  } else {
    decisionsTbody.innerHTML = ranked.slice(0, 10).map(row => {
      const sym = row.symbol || "—";
      const c = candidateBySym[sym];
      const dir = c ? c.direction : (row.direction || "—");
      const dirClass = dir === "BUY" || dir === "long" ? "dir-long" : (dir === "SELL" || dir === "short" ? "dir-short" : "dir-flat");
      const score = row.total_score || 0;
      const confidence = c ? c.confidence : null;
      const status = c ? '<span class="pill good">candidate</span>' : '<span class="pill">watching</span>';
      return `<tr>
        <td><b>${sym}</b></td>
        <td class="${dirClass}">${dir}</td>
        <td class="num"><span class="score-bar"><i style="width:${Math.min(100, score)}%"></i></span>${fmtNum(score, 1)}</td>
        <td class="num">${fmtNum(confidence, 1)}</td>
        <td>${status}</td>
      </tr>`;
    }).join("");
  }

  // positions table
  const positionsTbody = document.getElementById("positions-tbody");
  const positions = s.positions || [];
  if (positions.length === 0) {
    positionsTbody.innerHTML = '<tr><td colspan="5" class="empty">none right now — bot is flat</td></tr>';
  } else {
    positionsTbody.innerHTML = positions.map(p => {
      const m = p.market || p;
      const pos = p.position || p;
      const sym = (m.epic || pos.epic || "").split(".")[2] || "—";
      const dir = (pos.direction || pos.dealDirection || "").toLowerCase();
      const dirClass = dir.startsWith("buy") ? "dir-long" : (dir.startsWith("sell") ? "dir-short" : "dir-flat");
      const size = pos.size || pos.dealSize || "—";
      const entry = pos.openLevel || pos.level || "—";
      const upnl = pos.profit || pos.pnl || pos.unrealizedPnL || "—";
      return `<tr>
        <td><b>${sym}</b></td>
        <td class="${dirClass}">${dir.toUpperCase()}</td>
        <td class="num">${size}</td>
        <td class="num">${entry}</td>
        <td class="num">${upnl}</td>
      </tr>`;
    }).join("");
  }

  // MTF diagnostics
  const mtfTbody = document.getElementById("mtf-tbody");
  const mtf = s.mtf_diagnostics || {};
  const mtfRows = Object.keys(mtf);
  if (mtfRows.length === 0) {
    mtfTbody.innerHTML = '<tr><td colspan="3" class="empty">no MTF data this cycle</td></tr>';
  } else {
    mtfTbody.innerHTML = mtfRows.map(epic => {
      const d = mtf[epic] || {};
      const sym = epic.split(".")[2] || epic;
      const degraded = d.degraded;
      const sources = d.sources || {};
      const sourcesStr = Object.entries(sources).map(([k,v]) => `${k}:${v}`).join(" ");
      const modePill = degraded ? '<span class="pill warn">DEGRADED</span>' : '<span class="pill good">REAL</span>';
      return `<tr><td><b>${sym}</b></td><td>${modePill}</td><td style="color:var(--text-2);font-size:11px;">${sourcesStr || "—"}</td></tr>`;
    }).join("");
  }

  // Cost cap rows
  const costRows = (s.cost_cap || {}).rows || [];
  const costEl = document.getElementById("costcap-rows");
  if (costRows.length === 0) {
    costEl.innerHTML = '<div class="empty">no cost cap data</div>';
  } else {
    costEl.innerHTML = costRows.map(c => {
      const cls = c.pct >= 80 ? "bad" : "";
      return `
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:11px;">
            <span style="color:var(--text-1);">${c.category}</span>
            <span class="num">${fmtNum(c.used, 0)} / ${fmtNum(c.cap, 0)}</span>
          </div>
          <div class="progress ${cls}"><i style="width:${Math.min(100, c.pct)}%"></i></div>
        </div>`;
    }).join("");
  }

  // Shadow signals
  const shadow = s.shadow || {};
  const tiers = shadow.by_tier || {};
  const shadowEl = document.getElementById("shadow-rows");
  const tierKeys = Object.keys(tiers);
  if (tierKeys.length === 0) {
    shadowEl.innerHTML = '<div class="empty">no shadow data yet — needs ~1h of live cycles</div>';
  } else {
    shadowEl.innerHTML = `<div style="font-size:11px;color:var(--text-2);margin-bottom:10px;">${shadow.records} records over ${shadow.window_hours}h</div>` +
      tierKeys.map(t => {
        const r = tiers[t] || {};
        const wt = r.would_trade || 0;
        const ct = r.count || 0;
        const pct = ct > 0 ? Math.round(wt / ct * 100) : 0;
        return `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line);">
          <span style="color:var(--text-1);">${t}</span>
          <span><b>${wt}</b> / ${ct} would trade <span style="color:var(--text-2);">(${pct}%)</span></span>
        </div>`;
      }).join("");
  }

  // Score chart
  if (ranked.length > 0) {
    const labels = ranked.slice(0, 10).map(r => r.symbol);
    const values = ranked.slice(0, 10).map(r => r.total_score || 0);
    if (scoreChart) {
      scoreChart.data.labels = labels;
      scoreChart.data.datasets[0].data = values;
      scoreChart.update("none");
    } else {
      const ctx = document.getElementById("score-chart").getContext("2d");
      scoreChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [{
            label: "score",
            data: values,
            backgroundColor: values.map(v => v >= 74 ? "#4ade80" : (v >= 65 ? "#fbbf24" : "#60a5fa")),
            borderRadius: 4,
          }],
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, max: 100, grid: { color: "#232c44" }, ticks: { color: "#9ba8c1" } },
            x: { grid: { display: false }, ticks: { color: "#9ba8c1" } },
          },
        },
      });
    }
  }
}

// initial fetch + auto-refresh
tick();
setInterval(tick, 5000);
</script>

</body>
</html>
"""
