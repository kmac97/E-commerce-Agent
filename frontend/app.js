// app.js — E-commerce AI Agent Dashboard

const API_URL = window.API_URL || "https://e-comagent.duckdns.org";

// Lookup caches so we never embed JSON in onclick attributes
const _research = {};
const _products = {};
const _chatHistory = [];

// Full data arrays for client-side search
let _researchData = [];
let _productsData = [];

// Sort state
let _researchSort = 'date';
let _productsSort = 'date';

// Score filter state
let _researchScore7 = false;
let _productsScore7 = false;

// Last loaded timestamps per tab
const _lastLoaded = {};

// ─────────────────────────────────────────
// API
// ─────────────────────────────────────────

async function apiFetch(path, method = "GET", body = null) {
  try {
    const opts = { method };
    if (body) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(`${API_URL}${path}`, opts);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error (${path}):`, e);
    return null;
  }
}

// ─────────────────────────────────────────
// STATUS
// ─────────────────────────────────────────

async function checkStatus() {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  const data = await apiFetch("/health");
  if (data && data.status === "ok") {
    dot.className = "status-dot online";
    if (label) label.textContent = "Live";
    const tgBtn = document.getElementById("tg-btn");
    if (tgBtn && data.telegram_bot) {
      tgBtn.href = `https://t.me/${data.telegram_bot}`;
      tgBtn.classList.remove("hidden");
    }
  } else {
    dot.className = "status-dot offline";
    if (label) label.textContent = "Offline";
  }
}

// ─────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────

function showToast(msg, undoFn = null, type = "success") {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.innerHTML = `<span>${msg}</span>${undoFn ? '<button class="toast-undo">Undo</button>' : ""}`;
  document.body.appendChild(t);
  if (undoFn) {
    t.querySelector(".toast-undo").addEventListener("click", () => { undoFn(); t.remove(); });
  }
  requestAnimationFrame(() => t.classList.add("show"));
  setTimeout(() => { t.classList.remove("show"); setTimeout(() => t.remove(), 300); }, 4000);
}

// ─────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────

function animateStat(id, value) {
  const el = document.getElementById(id);
  const n = parseInt(value);
  if (isNaN(n)) { el.textContent = value; return; }
  const from = parseInt(el.textContent) || 0;
  if (from === n) return;
  const start = performance.now();
  const dur = Math.min(600, 100 + n * 40);
  const tick = (now) => {
    const t = Math.min((now - start) / dur, 1);
    el.textContent = Math.round(from + (n - from) * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function setTabMeta(tabId, refreshCall) {
  _lastLoaded[tabId] = Date.now();
  const el = document.getElementById(`meta-${tabId}`);
  if (!el) return;
  el.innerHTML = `<span>Updated just now</span><button class="tab-meta-refresh" onclick="${refreshCall}" title="Refresh">↻</button>`;
}

function updateTabMetas() {
  const now = Date.now();
  const refreshCalls = {
    research: "loadResearch(currentResearchFilter)",
    products: "loadProducts()",
    tasks: "loadTasks()",
  };
  for (const [tabId, ts] of Object.entries(_lastLoaded)) {
    const el = document.getElementById(`meta-${tabId}`);
    const refreshCall = refreshCalls[tabId];
    if (!el || !refreshCall) continue;
    const mins = Math.floor((now - ts) / 60000);
    const label = mins < 1 ? "just now" : mins === 1 ? "1m ago" : `${mins}m ago`;
    el.innerHTML = `<span>Updated ${label}</span><button class="tab-meta-refresh" onclick="${refreshCall}" title="Refresh">↻</button>`;
  }
}

function badge(type, text) {
  return `<span class="badge badge-${type}">${text}</span>`;
}

function scoreEl(score) {
  if (!score) return "";
  const cls = score >= 7 ? "score-high" : score >= 5 ? "score-mid" : "score-low";
  return `<span class="score ${cls}">${score}/10</span>`;
}

function deleteBtn(onclick) {
  return `<button class="btn-delete" onclick="event.stopPropagation();${onclick}" title="Delete">×</button>`;
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function inlineMd(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="md-code">$1</code>');
}

function renderMarkdown(text) {
  if (!text) return '';
  const lines = text.split('\n');
  let html = '';
  let inUl = false, inOl = false;
  const closeList = () => {
    if (inUl) { html += '</ul>'; inUl = false; }
    if (inOl) { html += '</ol>'; inOl = false; }
  };
  for (const line of lines) {
    if (/^## /.test(line)) {
      closeList();
      html += `<h3 class="md-h2">${inlineMd(line.slice(3))}</h3>`;
    } else if (/^# /.test(line)) {
      closeList();
      html += `<h2 class="md-h1">${inlineMd(line.slice(2))}</h2>`;
    } else if (/^[-*] /.test(line)) {
      if (inOl) { html += '</ol>'; inOl = false; }
      if (!inUl) { html += '<ul class="md-list">'; inUl = true; }
      html += `<li>${inlineMd(line.slice(2))}</li>`;
    } else if (/^\d+\. /.test(line)) {
      if (inUl) { html += '</ul>'; inUl = false; }
      if (!inOl) { html += '<ol class="md-list">'; inOl = true; }
      html += `<li>${inlineMd(line.replace(/^\d+\. /, ''))}</li>`;
    } else if (line.trim() === '') {
      closeList();
    } else {
      closeList();
      html += `<p class="md-p">${inlineMd(line)}</p>`;
    }
  }
  closeList();
  return html;
}

// ─────────────────────────────────────────
// DELETE (toast + undo)
// ─────────────────────────────────────────

async function deleteResearch(id, el) {
  const card = el.closest(".card");
  card.classList.add("card-fading");
  let cancelled = false;
  showToast("Research deleted", () => { cancelled = true; card.classList.remove("card-fading"); });
  setTimeout(async () => {
    if (cancelled) return;
    const res = await apiFetch(`/api/research/${id}`, "DELETE");
    if (res !== null) card.remove();
    else { card.classList.remove("card-fading"); showToast("Delete failed", null, "error"); }
  }, 4000);
}

async function deleteProduct(id, el) {
  const card = el.closest(".card");
  card.classList.add("card-fading");
  let cancelled = false;
  showToast("Product deleted", () => { cancelled = true; card.classList.remove("card-fading"); });
  setTimeout(async () => {
    if (cancelled) return;
    const res = await apiFetch(`/api/dashboard/products/${id}`, "DELETE");
    if (res !== null) card.remove();
    else { card.classList.remove("card-fading"); showToast("Delete failed", null, "error"); }
  }, 4000);
}

// ─────────────────────────────────────────
// STATUS PICKER
// ─────────────────────────────────────────

function editStatus(productId, currentStatus, el) {
  const select = document.createElement("select");
  select.className = "status-select";
  ["idea","researching","testing","active","dropped"].forEach(s => {
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s; opt.selected = s === currentStatus;
    select.appendChild(opt);
  });

  const restore = (status) => {
    const b = document.createElement("span");
    b.className = `badge badge-${status}`;
    b.textContent = status;
    b.setAttribute("onclick", `event.stopPropagation();editStatus('${productId}','${status}',this)`);
    if (select.parentNode) select.replaceWith(b);
  };

  el.replaceWith(select);
  select.focus();

  select.addEventListener("change", async () => {
    const newStatus = select.value;
    restore(newStatus);
    const res = await apiFetch(`/api/dashboard/products/${productId}/status`, "PATCH", { status: newStatus });
    if (res) { _products[productId].status = newStatus; showToast(`Status → ${newStatus}`); }
    else showToast("Update failed", null, "error");
  });
  select.addEventListener("blur", () => restore(currentStatus));
}

// ─────────────────────────────────────────
// BRIEFING
// ─────────────────────────────────────────

async function loadBriefing() {
  const data = await apiFetch("/api/dashboard/briefing");
  if (!data) { document.getElementById("briefing-card").style.display = "none"; return; }

  document.getElementById("briefing-date").textContent = data.date;
  if (data.tip) {
    const tipEl = document.getElementById("briefing-tip");
    tipEl.textContent = data.tip;
    tipEl.style.color = "";
  }

  const items = [];
  if (data.orders) items.push(`🛒 ${data.orders.count} orders · $${data.orders.revenue} ${data.orders.currency}`);
  else items.push("🛒 Shopify not connected");
  items.push(`🔍 ${data.research?.length ?? 0} items researched`);
  items.push(`⚡ ${data.tasks?.completed ?? 0} done · ${data.tasks?.failed ?? 0} failed`);
  document.getElementById("briefing-stats").innerHTML = items.map(i => `<span class="briefing-stat">${i}</span>`).join("");
}

// ─────────────────────────────────────────
// DASHBOARD TAB
// ─────────────────────────────────────────

async function loadDashboard() {
  loadBriefing(); // non-blocking
  const data = await apiFetch("/api/dashboard/summary");
  if (!data) {
    document.getElementById("recent-tasks").innerHTML = '<div class="empty">Could not reach server.</div>';
    document.getElementById("recent-research").innerHTML = '<div class="empty">Could not reach server.</div>';
    return;
  }

  const active = (data.recent_tasks || []).filter(t => t.status === "running").length;
  animateStat("stat-products", data.products?.length ?? 0);
  animateStat("stat-research", data.recent_research?.length ?? 0);
  animateStat("stat-tasks", data.recent_tasks?.length ?? 0);
  animateStat("stat-active", active);

  const statusCounts = {};
  (data.products || []).forEach(p => {
    const s = p.status || "idea";
    statusCounts[s] = (statusCounts[s] || 0) + 1;
  });
  const bEl = document.getElementById("status-breakdown");
  if (bEl) {
    const order = ["idea", "researching", "testing", "active", "dropped"];
    bEl.innerHTML = order
      .filter(s => statusCounts[s])
      .map(s => `<span class="badge badge-${s}">${statusCounts[s]} ${s}</span>`)
      .join("") || "";
  }

  const tasksEl = document.getElementById("recent-tasks");
  if (!data.recent_tasks?.length) {
    tasksEl.innerHTML = '<div class="empty">No agent tasks yet. Use /research in Telegram to start.</div>';
  } else {
    tasksEl.innerHTML = data.recent_tasks.slice(0, 5).map(t => `
      <div class="card">
        <div class="card-header">
          <div class="card-title">${t.task || t.agent}</div>
          ${badge(t.status, t.status)}
        </div>
        <div class="card-meta">${t.agent} · ${timeAgo(t.created_at)}</div>
      </div>
    `).join("");
  }

  const researchEl = document.getElementById("recent-research");
  if (!data.recent_research?.length) {
    researchEl.innerHTML = '<div class="empty">No research saved yet.</div>';
  } else {
    data.recent_research.forEach(r => _research[r.id] = r);
    researchEl.innerHTML = data.recent_research.slice(0, 5).map(r => `
      <div class="card" onclick="openResearch('${r.id}')">
        <div class="card-header">
          <div class="card-title">${r.topic}</div>
          <div style="display:flex;gap:6px;align-items:center">
            ${r.score ? scoreEl(r.score) : ""}
            ${badge(r.type, r.type)}
            ${deleteBtn(`deleteResearch('${r.id}',this)`)}
          </div>
        </div>
        <div class="card-meta">${timeAgo(r.created_at)}</div>
      </div>
    `).join("");
  }
}

// ─────────────────────────────────────────
// RESEARCH TAB
// ─────────────────────────────────────────

let currentResearchFilter = "";

async function loadResearch(type = "") {
  currentResearchFilter = type;
  const url = type ? `/api/research/?type=${type}&limit=50` : "/api/research/?limit=50";
  const data = await apiFetch(url);
  if (!data) { document.getElementById("research-list").innerHTML = '<div class="empty">Could not reach server.</div>'; return; }
  _researchData = data;
  data.forEach(r => _research[r.id] = r);
  renderResearch();
  setTabMeta("research", "loadResearch(currentResearchFilter)");
}

function setResearchSort(key) {
  _researchSort = key;
  document.querySelectorAll('[id^="research-sort-"]').forEach(b => b.classList.remove('active'));
  document.getElementById(`research-sort-${key}`)?.classList.add('active');
  renderResearch();
}

function toggleResearchScore7() {
  _researchScore7 = !_researchScore7;
  document.getElementById('research-score7')?.classList.toggle('active', _researchScore7);
  renderResearch();
}

function renderResearch() {
  const query = (document.getElementById("research-search")?.value || "").toLowerCase();
  const filtered = query
    ? _researchData.filter(r => (r.topic || "").toLowerCase().includes(query) || (r.notes || "").toLowerCase().includes(query))
    : _researchData;
  const sorted = _researchSort === 'score'
    ? [...filtered].sort((a, b) => (b.score || 0) - (a.score || 0))
    : filtered;
  const displayed = _researchScore7 ? sorted.filter(r => (r.score || 0) >= 7) : sorted;
  const el = document.getElementById("research-list");
  if (!displayed.length) {
    el.innerHTML = _researchScore7
      ? `<div class="empty">No research with score 7+ yet.</div>`
      : query
        ? `<div class="empty">No results for "${query}".</div>`
        : `<div class="empty-cta"><div class="empty-cta-icon">🔬</div><div class="empty-cta-text">No research saved yet</div><button class="empty-cta-btn" onclick="showAddResearch()">+ Start Research</button></div>`;
    return;
  }
  el.innerHTML = displayed.map(r => `
    <div class="card" onclick="openResearch('${r.id}')">
      <div class="card-header">
        <div class="card-title">${r.topic}</div>
        <div style="display:flex;gap:6px;align-items:center">
          ${r.score ? scoreEl(r.score) : ""}
          ${badge(r.type, r.type)}
          ${deleteBtn(`deleteResearch('${r.id}',this)`)}
        </div>
      </div>
      <div class="card-meta">${timeAgo(r.created_at)}</div>
      ${r.notes ? `<div class="card-snippet">${r.notes}</div>` : ""}
    </div>
  `).join("");
}

function searchResearch(query) { renderResearch(); }

// ─────────────────────────────────────────
// PRODUCTS TAB
// ─────────────────────────────────────────

async function loadProducts(status = "") {
  const url = status ? `/api/dashboard/products?status=${status}` : "/api/dashboard/products";
  const data = await apiFetch(url);
  if (!data) { document.getElementById("product-list").innerHTML = '<div class="empty">Could not reach server.</div>'; return; }
  _productsData = data;
  data.forEach(p => _products[p.id] = p);
  renderProducts();
  setTabMeta("products", "loadProducts()");
}

function setProductsSort(key) {
  _productsSort = key;
  document.querySelectorAll('[id^="products-sort-"]').forEach(b => b.classList.remove('active'));
  document.getElementById(`products-sort-${key}`)?.classList.add('active');
  renderProducts();
}

function toggleProductsScore7() {
  _productsScore7 = !_productsScore7;
  document.getElementById('products-score7')?.classList.toggle('active', _productsScore7);
  renderProducts();
}

function renderProducts() {
  const query = (document.getElementById("products-search")?.value || "").toLowerCase();
  const filtered = query
    ? _productsData.filter(p =>
        (p.name || "").toLowerCase().includes(query) ||
        (p.niche || "").toLowerCase().includes(query) ||
        (p.notes || "").toLowerCase().includes(query))
    : _productsData;
  const sorted = _productsSort === 'score'
    ? [...filtered].sort((a, b) => (b.score || 0) - (a.score || 0))
    : filtered;
  const displayed = _productsScore7 ? sorted.filter(p => (p.score || 0) >= 7) : sorted;
  const el = document.getElementById("product-list");
  if (!displayed.length) {
    el.innerHTML = _productsScore7
      ? `<div class="empty">No products with score 7+ yet.</div>`
      : query
        ? `<div class="empty">No results for "${query}".</div>`
        : `<div class="empty-cta"><div class="empty-cta-icon">📦</div><div class="empty-cta-text">No products in pipeline yet</div><button class="empty-cta-btn" onclick="showAddProduct()">+ Add Product</button></div>`;
    return;
  }
  el.innerHTML = displayed.map(p => `
    <div class="card" onclick="openProduct('${p.id}')">
      <div class="card-header">
        <div class="card-title">${p.name}</div>
        <div style="display:flex;gap:6px;align-items:center">
          ${p.score ? scoreEl(p.score) : ""}
          <span class="badge badge-${p.status || 'idea'}" onclick="event.stopPropagation();editStatus('${p.id}','${p.status || 'idea'}',this)">${p.status || "idea"}</span>
          ${deleteBtn(`deleteProduct('${p.id}',this)`)}
        </div>
      </div>
      ${p.niche ? `<div class="card-meta">Niche: ${p.niche}</div>` : ""}
      ${p.margin_estimate ? `<div class="card-meta">Est. margin: ${p.margin_estimate}%</div>` : ""}
      ${p.notes ? `<div class="card-snippet">${p.notes}</div>` : ""}
    </div>
  `).join("");
}

function searchProducts(query) { renderProducts(); }

// ─────────────────────────────────────────
// TASKS TAB
// ─────────────────────────────────────────

async function loadTasks() {
  const data = await apiFetch("/api/dashboard/tasks?limit=30");
  const el = document.getElementById("task-list");

  if (!data || !data.length) {
    el.innerHTML = '<div class="empty">No agent tasks yet.</div>';
    return;
  }

  el.innerHTML = data.map(t => `
    <div class="card">
      <div class="card-header">
        <div class="card-title">${t.task}</div>
        ${badge(t.status, t.status)}
      </div>
      <div class="card-meta">${t.agent} · ${timeAgo(t.created_at)}
        ${t.duration_seconds ? ` · ${t.duration_seconds}s` : ""}
      </div>
      ${t.error ? `<div class="card-snippet" style="color:#fca5a5">${t.error}</div>` : ""}
      ${t.status === "running" ? `<div class="task-running-bar"></div>` : ""}
    </div>
  `).join("");
  setTabMeta("tasks", "loadTasks()");
}

// ─────────────────────────────────────────
// VIEW MODALS
// ─────────────────────────────────────────

function openResearch(id) {
  const r = _research[id];
  if (!r) return;
  const raw = r.data?.raw_output;
  const body = raw
    ? `<div class="md-body">${renderMarkdown(raw)}</div>`
    : `<pre>${JSON.stringify(r.data || {}, null, 2)}</pre>`;
  document.getElementById("modal-content").innerHTML = `
    <h2>${r.topic}</h2>
    <div class="modal-badges">${badge(r.type, r.type)} ${r.score ? scoreEl(r.score) : ""}</div>
    ${r.notes ? `<div class="modal-section-label">Notes</div><p class="modal-body">${r.notes}</p>` : ""}
    <div class="modal-section-label">Research Output</div>
    ${body}
    <div class="modal-actions">
      <button class="btn-to-pipeline" onclick="researchToPipeline('${id}')">+ Add to Pipeline</button>
      <button class="btn-copy" onclick="copyResearch('${id}')">⎘ Copy</button>
    </div>
  `;
  document.getElementById("research-modal").classList.remove("hidden");
}

function downloadCSV(filename, rows) {
  const csv = rows.map(r => r.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = filename;
  a.click();
}

function exportResearchCSV() {
  if (!_researchData.length) { showToast("No research to export", null, "error"); return; }
  const headers = ["Topic", "Type", "Score", "Notes", "Created"];
  const rows = _researchData.map(r => [r.topic, r.type, r.score ?? "", r.notes ?? "", r.created_at?.slice(0,10) ?? ""]);
  downloadCSV("research.csv", [headers, ...rows]);
  showToast("Exported research.csv");
}

function exportProductsCSV() {
  if (!_productsData.length) { showToast("No products to export", null, "error"); return; }
  const headers = ["Name", "Status", "Score", "Niche", "Cost", "Sell Price", "Margin %", "Notes", "Created"];
  const rows = _productsData.map(p => [
    p.name, p.status ?? "idea", p.score ?? "", p.niche ?? "",
    p.cost_estimate ?? "", p.sell_price_estimate ?? "", p.margin_estimate ?? "",
    p.notes ?? "", p.created_at?.slice(0,10) ?? ""
  ]);
  downloadCSV("products.csv", [headers, ...rows]);
  showToast("Exported products.csv");
}

function copyResearch(id) {
  const r = _research[id];
  if (!r) return;
  const text = r.data?.raw_output || JSON.stringify(r.data || {}, null, 2);
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard"));
}

function researchToPipeline(id) {
  const r = _research[id];
  if (!r) return;
  closeModal();
  showAddProduct({ name: r.topic, score: r.score, notes: r.notes });
}

function openProduct(id) {
  const p = _products[id];
  if (!p) return;
  const metaItems = [
    p.niche            ? { key: "Niche",       val: p.niche }                      : null,
    p.cost_estimate    != null ? { key: "Cost",        val: `$${p.cost_estimate}` }        : null,
    p.sell_price_estimate != null ? { key: "Sell Price", val: `$${p.sell_price_estimate}` } : null,
    p.margin_estimate  != null ? { key: "Est. Margin", val: `${p.margin_estimate}%` }      : null,
  ].filter(Boolean);
  const metaHtml = metaItems.length ? `
    <div class="modal-section-label">Details</div>
    <div class="modal-meta">
      ${metaItems.map(m => `
        <div class="modal-meta-item">
          <span class="modal-meta-key">${m.key}</span>
          <span class="modal-meta-val">${m.val}</span>
        </div>
      `).join("")}
    </div>
  ` : "";
  document.getElementById("modal-content").innerHTML = `
    <h2>${p.name}</h2>
    <div class="modal-badges">${badge(p.status || "idea", p.status || "idea")} ${p.score ? scoreEl(p.score) : ""}</div>
    ${metaHtml}
    ${p.notes ? `<div class="modal-section-label">Notes</div><p class="modal-body">${p.notes}</p>` : ""}
    ${p.data ? `<div class="modal-section-label">Raw Data</div><pre>${JSON.stringify(p.data, null, 2)}</pre>` : ""}
    <div class="modal-actions">
      <button class="btn-edit" onclick="editProduct('${id}')">✎ Edit</button>
    </div>
  `;
  document.getElementById("research-modal").classList.remove("hidden");
}

function editProduct(id) {
  const p = _products[id];
  if (!p) return;
  document.getElementById("modal-content").innerHTML = `
    <h2 style="margin-bottom:18px;font-size:17px;font-weight:700;letter-spacing:-0.02em">Edit Product</h2>
    <div class="form-group">
      <label class="form-label">Name *</label>
      <input class="form-input" id="ep-name" value="${escHtml(p.name || '')}" />
    </div>
    <div class="form-group">
      <label class="form-label">Niche</label>
      <input class="form-input" id="ep-niche" value="${escHtml(p.niche || '')}" />
    </div>
    <div class="form-group">
      <label class="form-label">Score (1–10)</label>
      <input class="form-input" id="ep-score" type="number" min="1" max="10" value="${p.score || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Est. Cost ($)</label>
      <input class="form-input" id="ep-cost" type="number" step="0.01" value="${p.cost_estimate || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Est. Sell Price ($)</label>
      <input class="form-input" id="ep-sell" type="number" step="0.01" value="${p.sell_price_estimate || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-input" id="ep-notes" rows="3">${escHtml(p.notes || '')}</textarea>
    </div>
    <button class="form-submit" onclick="saveProductEdit('${id}')">Save Changes</button>
  `;
  setTimeout(() => document.getElementById("ep-name")?.focus(), 60);
}

async function saveProductEdit(id) {
  const name = document.getElementById("ep-name").value.trim();
  if (!name) { showToast("Name is required", null, "error"); return; }
  const btn = document.querySelector("#modal-content .form-submit");
  btn.disabled = true; btn.textContent = "Saving...";
  const fields = {
    name,
    niche: document.getElementById("ep-niche").value.trim() || null,
    score: parseInt(document.getElementById("ep-score").value) || null,
    cost_estimate: parseFloat(document.getElementById("ep-cost").value) || null,
    sell_price_estimate: parseFloat(document.getElementById("ep-sell").value) || null,
    notes: document.getElementById("ep-notes").value.trim() || null,
  };
  const res = await apiFetch(`/api/dashboard/products/${id}`, "PATCH", fields);
  if (res) {
    Object.assign(_products[id], fields);
    closeModal();
    showToast("Product updated");
    loadProducts();
  } else {
    btn.disabled = false; btn.textContent = "Save Changes";
    showToast("Update failed", null, "error");
  }
}

function closeModal() {
  document.getElementById("research-modal").classList.add("hidden");
}

document.getElementById("research-modal").addEventListener("click", function(e) {
  if (e.target === this) closeModal();
});

// ─────────────────────────────────────────
// ADD FORMS
// ─────────────────────────────────────────

function showAddProduct(prefill = {}) {
  document.getElementById("form-content").innerHTML = `
    <h2 style="margin-bottom:18px;font-size:17px;font-weight:700;letter-spacing:-0.02em">Add Product</h2>
    <div class="form-group">
      <label class="form-label">Name *</label>
      <input class="form-input" id="f-name" placeholder="e.g. Bamboo phone case" value="${prefill.name || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Niche</label>
      <input class="form-input" id="f-niche" placeholder="e.g. Eco-friendly accessories" value="${prefill.niche || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Score (1–10)</label>
      <input class="form-input" id="f-score" type="number" min="1" max="10" placeholder="Optional" value="${prefill.score || ''}" />
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-input" id="f-notes" rows="3" placeholder="Initial thoughts...">${prefill.notes || ''}</textarea>
    </div>
    <button class="form-submit" onclick="submitAddProduct()">Add to Pipeline</button>
  `;
  document.getElementById("form-modal").classList.remove("hidden");
  setTimeout(() => document.getElementById("f-name")?.focus(), 60);
}

async function submitAddProduct() {
  const name = document.getElementById("f-name").value.trim();
  if (!name) { showToast("Name is required", null, "error"); return; }
  const btn = document.querySelector("#form-content .form-submit");
  btn.disabled = true; btn.textContent = "Adding...";
  const res = await apiFetch("/api/dashboard/products", "POST", {
    name,
    niche: document.getElementById("f-niche").value.trim() || null,
    score: parseInt(document.getElementById("f-score").value) || null,
    notes: document.getElementById("f-notes").value.trim() || null,
  });
  if (res) { closeFormModal(); showToast("Product added"); loadProducts(); }
  else { btn.disabled = false; btn.textContent = "Add to Pipeline"; showToast("Failed to add", null, "error"); }
}

function showAddResearch() {
  document.getElementById("form-content").innerHTML = `
    <h2 style="margin-bottom:6px;font-size:17px;font-weight:700;letter-spacing:-0.02em">Research a Topic</h2>
    <p style="color:var(--muted);font-size:13px;margin-bottom:18px">The agent will investigate and save results automatically.</p>
    <div class="form-group">
      <label class="form-label">Topic *</label>
      <input class="form-input" id="f-topic" placeholder="e.g. Bamboo phone cases for iPhone 16" />
    </div>
    <div class="form-group">
      <label class="form-label">Type</label>
      <select class="form-input" id="f-type">
        <option value="product">Product</option>
        <option value="niche">Niche</option>
        <option value="competitor">Competitor</option>
      </select>
    </div>
    <button class="form-submit" onclick="submitAddResearch()">Start Research</button>
  `;
  document.getElementById("form-modal").classList.remove("hidden");
  setTimeout(() => document.getElementById("f-topic")?.focus(), 60);
}

async function submitAddResearch() {
  const topic = document.getElementById("f-topic").value.trim();
  if (!topic) { showToast("Topic is required", null, "error"); return; }
  const btn = document.querySelector("#form-content .form-submit");
  btn.disabled = true; btn.textContent = "Starting...";
  const res = await apiFetch("/api/agents/research", "POST", {
    topic,
    type: document.getElementById("f-type").value,
  });
  if (res) {
    closeFormModal();
    showToast(`Research started for "${topic}"`);
    pollTask(res.task_id, topic);
  } else {
    btn.disabled = false; btn.textContent = "Start Research";
    showToast("Failed to start", null, "error");
  }
}

function pollTask(taskId, label) {
  if (!taskId) return;
  const interval = setInterval(async () => {
    const task = await apiFetch(`/api/agents/status/${taskId}`);
    if (!task) return;
    if (task.status === "complete") {
      clearInterval(interval);
      showToast(`✓ Research done: "${label}"`);
      const activeTab = document.querySelector(".tab.active")?.dataset.tab;
      if (activeTab === "research") loadResearch(currentResearchFilter);
      if (activeTab === "dashboard") loadDashboard();
      if (activeTab === "tasks") loadTasks();
    } else if (task.status === "failed") {
      clearInterval(interval);
      showToast(`Research failed: "${label}"`, null, "error");
    }
  }, 5000);
  setTimeout(() => clearInterval(interval), 600000); // 10min max
}

function closeFormModal() {
  document.getElementById("form-modal").classList.add("hidden");
}

document.getElementById("form-modal").addEventListener("click", function(e) {
  if (e.target === this) closeFormModal();
});

// ─────────────────────────────────────────
// MAX CHAT
// ─────────────────────────────────────────

function sendPrompt(text) {
  const input = document.getElementById("chat-input");
  if (!input) return;
  input.value = text;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.querySelector(".chat-send");
  const msg = input.value.trim();
  if (!msg) return;

  input.value = "";
  input.disabled = true;
  sendBtn.disabled = true;

  appendChatMsg("user", msg);
  _chatHistory.push({ role: "user", content: msg });

  const typing = appendTyping();

  const data = await apiFetch("/api/agents/chat", "POST", {
    message: msg,
    history: _chatHistory.slice(-20),
  });

  typing.remove();

  const reply = data?.reply || "Sorry, I'm having trouble connecting right now.";
  appendChatMsg("assistant", reply);
  _chatHistory.push({ role: "assistant", content: reply });

  input.disabled = false;
  sendBtn.disabled = false;
  input.focus();
  scrollChat();
}

function appendChatMsg(role, text) {
  const msgs = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  const content = role === "assistant"
    ? renderMarkdown(text)
    : text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/\n/g,"<br>");
  div.innerHTML = `<div class="chat-bubble">${content}</div>`;
  msgs.appendChild(div);
  scrollChat();
}

function appendTyping() {
  const msgs = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "chat-msg assistant";
  div.innerHTML = '<div class="chat-bubble typing"><span></span><span></span><span></span></div>';
  msgs.appendChild(div);
  scrollChat();
  return div;
}

function scrollChat() {
  const msgs = document.getElementById("chat-messages");
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

// ─────────────────────────────────────────
// TAB SWITCHING
// ─────────────────────────────────────────

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    tab.classList.add("active");
    const target = document.getElementById(`tab-${tab.dataset.tab}`);
    if (target) target.classList.add("active");

    if (tab.dataset.tab === "dashboard") loadDashboard();
    if (tab.dataset.tab === "research") loadResearch(currentResearchFilter);
    if (tab.dataset.tab === "products") loadProducts();
    if (tab.dataset.tab === "tasks") loadTasks();
    if (tab.dataset.tab === "max") setTimeout(scrollChat, 50);
  });
});

// Filter buttons
document.querySelectorAll("#tab-research .filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tab-research .filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadResearch(btn.dataset.filter);
  });
});

document.querySelectorAll("#tab-products .filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tab-products .filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadProducts(btn.dataset.filter);
  });
});

// Chat: send on Enter
document.getElementById("chat-input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

// Stat card click-through
document.querySelectorAll(".stat-card[data-tab]").forEach(card => {
  card.addEventListener("click", () => {
    const tabBtn = document.querySelector(`.tab[data-tab="${card.dataset.tab}"]`);
    if (tabBtn) tabBtn.click();
  });
});

// ─────────────────────────────────────────
// KEYBOARD SHORTCUTS
// ─────────────────────────────────────────

document.addEventListener("keydown", e => {
  if (e.key === "Escape") { closeModal(); closeFormModal(); return; }
  if (e.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)) {
    e.preventDefault();
    const t = document.querySelector(".tab.active")?.dataset.tab;
    if (t === "research") document.getElementById("research-search")?.focus();
    else if (t === "products") document.getElementById("products-search")?.focus();
    else if (t === "max") document.getElementById("chat-input")?.focus();
  }
});

// ─────────────────────────────────────────
// INIT
// ─────────────────────────────────────────

checkStatus();
loadDashboard();

// Handle PWA shortcut deep-links (/?tab=research etc)
const _urlTab = new URLSearchParams(location.search).get("tab");
if (_urlTab) {
  const _tabBtn = document.querySelector(`.tab[data-tab="${_urlTab}"]`);
  if (_tabBtn) _tabBtn.click();
}

setInterval(() => {
  const activeTab = document.querySelector(".tab.active")?.dataset.tab;
  if (activeTab === "dashboard") loadDashboard();
  if (activeTab === "tasks") loadTasks();
  checkStatus();
  updateTabMetas();
}, 30000);
