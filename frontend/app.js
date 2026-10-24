"use strict";

const $ = (sel) => document.querySelector(sel);
const STATION_SECONDS = 7 * 60;

const state = {
  sessionId: null,
  timer: null,
  remaining: STATION_SECONDS,
  turn: 0,
};

// ---------- helpers ----------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = null;
  try { data = await res.json(); } catch { /* sin cuerpo */ }
  if (!res.ok) {
    const msg = (data && (data.error || JSON.stringify(data.detail))) || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    $("#tab-sim").hidden = btn.dataset.tab !== "sim";
    $("#tab-rag").hidden = btn.dataset.tab !== "rag";
  });
});

api("/api/health").then((h) => { $("#backend").textContent = `backend: ${h.backend}`; }).catch(() => {});

// ---------- case picker ----------
async function loadCases() {
  const box = $("#cases");
  box.textContent = "Cargando casos…";
  try {
    const cases = await api(`/api/cases?materia=${encodeURIComponent($("#materia").value)}`);
    box.textContent = "";
    if (!cases.length) box.textContent = "No hay casos para esta materia.";
    for (const c of cases) {
      const card = el("button", "card");
      card.type = "button";
      card.append(el("h3", null, c.titulo));
      const p = c.paciente || {};
      card.append(el("div", "small", `${p.nombre ?? "—"} · ${p.edad ?? "?"} años · ${p.sexo ?? "?"}`));
      const meta = el("div", "small");
      meta.style.marginTop = "8px";
      meta.append(el("span", "pill", c.dificultad || "sin dificultad"));
      card.append(meta);
      card.addEventListener("click", () => startCase(c));
      box.append(card);
    }
  } catch (err) {
    box.textContent = `Error al cargar casos: ${err.message}`;
  }
}
$("#materia").addEventListener("change", loadCases);

async function startCase(c) {
  try {
    const { session_id } = await api("/api/sessions", {
      method: "POST", body: JSON.stringify({ case_id: c.id }),
    });
    state.sessionId = session_id;
  } catch (err) {
    alert(`No se pudo crear la sesión: ${err.message}`);
    return;
  }
  resetConsult();
  const p = c.paciente || {};
  $("#case-title").textContent = c.titulo;
  $("#case-patient").textContent = `${p.nombre ?? ""} · ${p.edad ?? "?"} años · ${p.sexo ?? ""}`;
  $("#picker").hidden = true;
  $("#consult").hidden = false;
  $("#input").focus();
}

function resetConsult() {
  clearInterval(state.timer);
  state.timer = null;
  state.remaining = STATION_SECONDS;
  state.turn = 0;
  renderTimer();
  $("#timer-warn").hidden = true;
  $("#chat").textContent = "";
  $("#debug-list").textContent = "";
  $("#summary").hidden = true;
  setBusy(false);
}

$("#btn-back").addEventListener("click", () => {
  clearInterval(state.timer);
  state.sessionId = null;
  $("#consult").hidden = true;
  $("#picker").hidden = false;
});

$("#btn-debug").addEventListener("click", () => { $("#debug").hidden = !$("#debug").hidden; });

// ---------- timer ----------
function renderTimer() {
  const r = Math.abs(state.remaining);
  const txt = `${state.remaining < 0 ? "-" : ""}${Math.floor(r / 60)}:${String(r % 60).padStart(2, "0")}`;
  $("#timer").textContent = txt;
  $("#timer").classList.toggle("over", state.remaining <= 0);
}

function startTimer() {
  if (state.timer) return;
  state.timer = setInterval(() => {
    state.remaining -= 1;
    renderTimer();
    if (state.remaining === 0) $("#timer-warn").hidden = false;
  }, 1000);
}

// ---------- chat ----------
const LABELS = { estudiante: "Vos", paciente: "Paciente", docente: "Docente" };

function addMsg(role, text) {
  const m = el("div", `msg ${role}`);
  m.append(el("span", "who", LABELS[role] || role));
  m.append(document.createTextNode(text));
  const chat = $("#chat");
  chat.append(m);
  chat.scrollTop = chat.scrollHeight;
}

function setBusy(busy) {
  $("#input").disabled = busy;
  $("#btn-send").disabled = busy;
  $("#typing").hidden = !busy;
}

function addDebug(question, debug) {
  const d = el("div", "dbg");
  d.append(el("div", "q", `#${state.turn} · ${question}`));
  d.append(el("pre", null, JSON.stringify(debug, null, 2)));
  const list = $("#debug-list");
  list.prepend(d);
}

async function sendMessage() {
  const text = $("#input").value.trim();
  if (!text || !state.sessionId) return;
  startTimer();
  $("#input").value = "";
  addMsg("estudiante", text);
  setBusy(true);
  state.turn += 1;
  try {
    const res = await api(`/api/sessions/${state.sessionId}/messages`, {
      method: "POST", body: JSON.stringify({ text }),
    });
    for (const r of res.replies || []) addMsg(r.role, r.text);
    addDebug(text, res.debug);
  } catch (err) {
    addMsg("error", `Error del agente: ${err.message}`);
    addDebug(text, { error: err.message });
  } finally {
    setBusy(false);
    $("#input").focus();
  }
}

$("#composer").addEventListener("submit", (e) => { e.preventDefault(); sendMessage(); });
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ---------- resumen ----------
$("#btn-end").addEventListener("click", async () => {
  if (!state.sessionId) return;
  clearInterval(state.timer);
  try {
    const s = await api(`/api/sessions/${state.sessionId}/finish`, { method: "POST" });
    const revealed = (s.revealed_facts || []).length;
    const total = s.total_facts || 0;
    $("#sum-facts").textContent = `${revealed} / ${total}`;
    $("#sum-bar").style.width = total ? `${Math.round((100 * revealed) / total)}%` : "0";
    const list = (xs) => (xs && xs.length ? xs.join(", ") : "—");
    $("#sum-exams").textContent = list(s.exams_done);
    $("#sum-studies").textContent = list(s.studies_requested);
    $("#sum-dx").textContent = s.diagnosis_proposed || "—";
    $("#summary").hidden = false;
    $("#summary").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    addMsg("error", `No se pudo obtener el resumen: ${err.message}`);
  }
});

// ---------- RAG ----------
$("#rag-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#rag-q").value.trim();
  if (!q) return;
  const params = new URLSearchParams({
    q, materia: "mpna", k: $("#rag-k").value || "5", tipo: $("#rag-tipo").value,
  });
  const out = $("#rag-results");
  out.textContent = "";
  $("#rag-status").textContent = "Buscando…";
  const t0 = performance.now();
  try {
    const results = await api(`/api/rag/search?${params}`);
    $("#rag-status").textContent = `${results.length} resultados en ${Math.round(performance.now() - t0)} ms (score: menor = más cercano)`;
    for (const r of results) {
      const m = r.metadata || {};
      const card = el("div", "rag-card");
      const meta = el("div", "rag-meta");
      meta.append(el("span", "src", m.fuente || "?"));
      meta.append(el("span", "muted", `p. ${m.pagina ?? "?"}`));
      if (m.seccion) meta.append(el("span", "muted", m.seccion));
      meta.append(el("span", "pill", m.tipo || "?"));
      meta.append(el("span", "muted", `score ${Number(r.score).toFixed(3)}`));
      const txt = el("div", "rag-text", r.texto);
      const more = el("button", "ghost", "Ver más");
      more.type = "button";
      more.addEventListener("click", () => {
        const open = txt.classList.toggle("open");
        more.textContent = open ? "Ver menos" : "Ver más";
      });
      card.append(meta, txt, more);
      out.append(card);
    }
  } catch (err) {
    $("#rag-status").textContent = `Error: ${err.message}`;
  }
});

loadCases();
