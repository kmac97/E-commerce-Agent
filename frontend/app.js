// app.js — E-commerce AI Agent Dashboard

const API_URL = window.API_URL || "https://e-comagent.duckdns.org";

// Lookup caches so we never embed JSON in onclick attributes
const _research = {};
const _products = {};
const _chatHistory = [];

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
  const el = document.getElementById("research-list");

  if (!data || !data.length) {
    el.innerHTML = '<div class="empty">No research saved yet.</div>';
    return;
  }

  data.forEach(r => _research[r.id] = r);
  el.innerHTML = data.map(r => `
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

  data.forEach(p => _products[p.id] = p);
  el.innerHTML = data.map(p => `
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
// VIEW MODALS
// ─────────────────────────────────────────

function openResearch(id) {
  const r = _research[id];
  if (!r) return;
  const rawOutput = r.data?.raw_output || JSON.stringify(r.data || {}, null, 2);
  document.getElementById("modal-content").innerHTML = `
    <h2>${r.topic}</h2>
    <p style="margin-bottom:10px">${badge(r.type, r.type)} ${r.score ? scoreEl(r.score) : ""}</p>
    <pre>${rawOutput}</pre>
  `;
  document.getElementById("research-modal").classList.remove("hidden");
}

function openProduct(id) {
  const p = _products[id];
  if (!p) return;
  const meta = [
    p.niche ? `Niche: ${p.niche}` : null,
    p.cost_estimate != null ? `Cost: $${p.cost_estimate}` : null,
    p.sell_price_estimate != null ? `Sell price: $${p.sell_price_estimate}` : null,
    p.margin_estimate != null ? `Margin: ${p.margin_estimate}%` : null,
  ].filter(Boolean).join(" · ");
  document.getElementById("modal-content").innerHTML = `
    <h2>${p.name}</h2>
    <p style="margin-bottom:10px">${badge(p.status || "idea", p.status || "idea")} ${p.score ? scoreEl(p.score) : ""}</p>
    ${meta ? `<p style="margin-bottom:10px;font-size:13px;color:var(--muted2)">${meta}</p>` : ""}
    ${p.notes ? `<p>${p.notes}</p>` : ""}
    ${p.data ? `<pre>${JSON.stringify(p.data, null, 2)}</pre>` : ""}
  `;
  document.getElementById("research-modal").classList.remove("hidden");
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

function showAddProduct() {
  document.getElementById("form-content").innerHTML = `
    <h2 style="margin-bottom:18px;font-size:17px;font-weight:700;letter-spacing:-0.02em">Add Product</h2>
    <div class="form-group">
      <label class="form-label">Name *</label>
      <input class="form-input" id="f-name" placeholder="e.g. Bamboo phone case" />
    </div>
    <div class="form-group">
      <label class="form-label">Niche</label>
      <input class="form-input" id="f-niche" placeholder="e.g. Eco-friendly accessories" />
    </div>
    <div class="form-group">
      <label class="form-label">Score (1–10)</label>
      <input class="form-input" id="f-score" type="number" min="1" max="10" placeholder="Optional" />
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-input" id="f-notes" rows="3" placeholder="Initial thoughts..."></textarea>
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
  if (res) { closeFormModal(); showToast(`Research started for "${topic}"`); }
  else { btn.disabled = false; btn.textContent = "Start Research"; showToast("Failed to start", null, "error"); }
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
  div.innerHTML = `<div class="chat-bubble">${text.replace(/\n/g, "<br>")}</div>`;
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

// ─────────────────────────────────────────
// INIT
// ─────────────────────────────────────────

checkStatus();
loadDashboard();

setInterval(() => {
  const activeTab = document.querySelector(".tab.active")?.dataset.tab;
  if (activeTab === "dashboard") loadDashboard();
  if (activeTab === "tasks") loadTasks();
  checkStatus();
}, 30000);
