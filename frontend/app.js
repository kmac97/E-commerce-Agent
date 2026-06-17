// app.js — E-commerce AI Agent Dashboard

// ─────────────────────────────────────────
// CONFIG
// Set this to your Hostinger VPS IP/domain + port
// ─────────────────────────────────────────
const API_URL = window.API_URL || "http://148.230.120.176:8000";

// ─────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────

async function apiFetch(path) {
  try {
    const res = await fetch(`${API_URL}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error (${path}):`, e);
    return null;
  }
}

// ─────────────────────────────────────────
// CONNECTION STATUS
// ─────────────────────────────────────────

async function checkStatus() {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  const data = await apiFetch("/health");
  if (data && data.status === "ok") {
    dot.className = "status-dot online";
    if (label) label.textContent = "Live";
  } else {
    dot.className = "status-dot offline";
    if (label) label.textContent = "Offline";
  }
}

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

// ─────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────

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

function badge(type, text) {
  return `<span class="badge badge-${type}">${text}</span>`;
}

function scoreEl(score) {
  if (!score) return "";
  const cls = score >= 7 ? "score-high" : score >= 5 ? "score-mid" : "score-low";
  return `<span class="score ${cls}">${score}/10</span>`;
}

// ─────────────────────────────────────────
// DASHBOARD TAB
// ─────────────────────────────────────────

async function loadDashboard() {
  const data = await apiFetch("/api/dashboard/summary");
  if (!data) return;

  // Stats
  const active = (data.recent_tasks || []).filter(t => t.status === "running").length;
  animateStat("stat-products", data.products?.length ?? 0);
  animateStat("stat-research", data.recent_research?.length ?? 0);
  animateStat("stat-tasks", data.recent_tasks?.length ?? 0);
  animateStat("stat-active", active);

  // Recent tasks
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

  // Recent research
  const researchEl = document.getElementById("recent-research");
  if (!data.recent_research?.length) {
    researchEl.innerHTML = '<div class="empty">No research saved yet.</div>';
  } else {
    researchEl.innerHTML = data.recent_research.slice(0, 5).map(r => `
      <div class="card" onclick="openResearch('${r.id}', ${JSON.stringify(r).replace(/'/g, "\\'")})">
        <div class="card-header">
          <div class="card-title">${r.topic}</div>
          ${badge(r.type, r.type)}
        </div>
        <div class="card-meta">${timeAgo(r.created_at)}${r.score ? ` · ${scoreEl(r.score)}` : ""}</div>
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
  const el = document.getElementById("research-list");

  if (!data || !data.length) {
    el.innerHTML = '<div class="empty">No research saved yet.</div>';
    return;
  }

  el.innerHTML = data.map(r => `
    <div class="card" onclick="openResearch('${r.id}', ${JSON.stringify(r).replace(/'/g, "\\'")})">
      <div class="card-header">
        <div class="card-title">${r.topic}</div>
        <div style="display:flex;gap:6px;align-items:center">
          ${r.score ? scoreEl(r.score) : ""}
          ${badge(r.type, r.type)}
        </div>
      </div>
      <div class="card-meta">${timeAgo(r.created_at)}</div>
      ${r.notes ? `<div class="card-snippet">${r.notes}</div>` : ""}
    </div>
  `).join("");
}

// ─────────────────────────────────────────
// PRODUCTS TAB
// ─────────────────────────────────────────

async function loadProducts(status = "") {
  const url = status ? `/api/dashboard/products?status=${status}` : "/api/dashboard/products";
  const data = await apiFetch(url);
  const el = document.getElementById("product-list");

  if (!data || !data.length) {
    el.innerHTML = '<div class="empty">No products in pipeline yet.</div>';
    return;
  }

  el.innerHTML = data.map(p => `
    <div class="card">
      <div class="card-header">
        <div class="card-title">${p.name}</div>
        <div style="display:flex;gap:6px;align-items:center">
          ${p.score ? scoreEl(p.score) : ""}
          ${badge(p.status || "idea", p.status || "idea")}
        </div>
      </div>
      ${p.niche ? `<div class="card-meta">Niche: ${p.niche}</div>` : ""}
      ${p.margin_estimate ? `<div class="card-meta">Est. margin: ${p.margin_estimate}%</div>` : ""}
      ${p.notes ? `<div class="card-snippet">${p.notes}</div>` : ""}
    </div>
  `).join("");
}

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
    </div>
  `).join("");
}

// ─────────────────────────────────────────
// MODAL
// ─────────────────────────────────────────

function openResearch(id, data) {
  const modal = document.getElementById("research-modal");
  const content = document.getElementById("modal-content");

  const rawOutput = data?.data?.raw_output || JSON.stringify(data?.data || {}, null, 2);

  content.innerHTML = `
    <h2>${data.topic}</h2>
    <p style="margin-bottom:10px">${badge(data.type, data.type)} ${data.score ? scoreEl(data.score) : ""}</p>
    <pre>${rawOutput}</pre>
  `;
  modal.classList.remove("hidden");
}

function closeModal() {
  document.getElementById("research-modal").classList.add("hidden");
}

document.getElementById("research-modal").addEventListener("click", function(e) {
  if (e.target === this) closeModal();
});

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

    // Load data for the tab
    if (tab.dataset.tab === "dashboard") loadDashboard();
    if (tab.dataset.tab === "research") loadResearch(currentResearchFilter);
    if (tab.dataset.tab === "products") loadProducts();
    if (tab.dataset.tab === "tasks") loadTasks();
  });
});

// ─────────────────────────────────────────
// FILTER BUTTONS
// ─────────────────────────────────────────

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

// ─────────────────────────────────────────
// INIT
// ─────────────────────────────────────────

checkStatus();
loadDashboard();

// Auto-refresh every 30 seconds
setInterval(() => {
  const activeTab = document.querySelector(".tab.active")?.dataset.tab;
  if (activeTab === "dashboard") loadDashboard();
  if (activeTab === "tasks") loadTasks();
  checkStatus();
}, 30000);
