const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: "DELETE" });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
};

async function errorFrom(r) {
  try {
    const data = await r.json();
    return new Error(data.detail || r.statusText);
  } catch {
    return new Error(r.statusText);
  }
}

let currentState = null;
let currentTopics = [];

// ------------------------------------------------------------- bootstrap

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  document.getElementById("regenerate-btn").addEventListener("click", onRegenerate);
  document.getElementById("add-topic-form").addEventListener("submit", onAddTopic);
  document.getElementById("add-question-form").addEventListener("submit", onAddQuestion);
  document.getElementById("editor-topic-select").addEventListener("change", onEditorTopicChange);
  loadAll();
});

function initTheme() {
  const saved = localStorage.getItem("dsa-theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", cur);
    localStorage.setItem("dsa-theme", cur);
  });
}

function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

async function loadAll() {
  await Promise.all([loadState(), loadToday(), loadProgressAndTopics()]);
}

// ---------------------------------------------------------------- state

async function loadState() {
  currentState = await api.get("/api/state");
  renderState(currentState);
}

function renderState(state) {
  document.getElementById("round-badge").textContent =
    `Round ${state.current_round} - ${state.current_round === 1 ? "Pen & Paper" : "Implementation"}`;
  document.getElementById("today-date").textContent = state.today;

  const weekendBanner = document.getElementById("weekend-banner");
  if (state.is_weekend && (state.locked_topics.length || state.pending_topics.length)) {
    let html = "";
    if (state.locked_topics.length) {
      html += `<h4>Want to unlock a new topic this weekend?</h4>`;
      html += state.locked_topics
        .map(
          (t) => `<span class="weekend-topic-chip">${escapeHtml(t.name)}
            <button class="btn btn-sm btn-primary" data-unlock="${t.id}">Unlock</button></span>`
        )
        .join("");
    }
    if (state.pending_topics.length) {
      html += `<h4 style="margin-top:12px;">Unlocked earlier, first pass not yet confirmed:</h4>`;
      html += state.pending_topics
        .map(
          (t) => `<span class="weekend-topic-chip">${escapeHtml(t.name)} (started ${t.started_at})
            <button class="btn btn-sm" data-confirm="${t.id}">Mark first pass done</button></span>`
        )
        .join("");
    }
    weekendBanner.innerHTML = html;
    weekendBanner.classList.remove("hidden");
    weekendBanner.querySelectorAll("[data-unlock]").forEach((b) =>
      b.addEventListener("click", () => onUnlockTopic(Number(b.dataset.unlock)))
    );
    weekendBanner.querySelectorAll("[data-confirm]").forEach((b) =>
      b.addEventListener("click", () => onConfirmFirstPass(Number(b.dataset.confirm)))
    );
  } else {
    weekendBanner.classList.add("hidden");
  }
}

// ---------------------------------------------------------------- today

async function loadToday() {
  const data = await api.get("/api/today");
  renderToday(data.questions);
}

function renderToday(questions) {
  const el = document.getElementById("today-list");
  if (!questions.length) {
    el.innerHTML = `<div class="empty-note">No questions available. Unlock or add more topics/questions.</div>`;
    return;
  }
  el.innerHTML = questions
    .map((q) => {
      const badgeClass = q.slot_type === "revision" ? "badge-revision" : "badge-fresh";
      const titleHtml = q.url
        ? `<a href="${escapeAttr(q.url)}" target="_blank" rel="noopener">${escapeHtml(q.title)}</a>`
        : escapeHtml(q.title);
      return `
      <div class="card" data-qid="${q.id}">
        <div class="q-card-top">
          <div>
            <div class="q-title">${titleHtml}</div>
            <div class="q-meta">
              <span>${escapeHtml(q.topic_name)}</span>
              ${q.difficulty ? `<span>${escapeHtml(q.difficulty)}</span>` : ""}
              <span>streak ${q.streak_stage}</span>
              <span>fails ${q.fail_count}</span>
            </div>
          </div>
          <span class="badge ${badgeClass}">${q.slot_type}</span>
        </div>
        <div class="q-actions">
          <button class="btn btn-solved" data-mark="solved">Solved</button>
          <button class="btn btn-failed" data-mark="not_solved">Not solved</button>
          <input type="text" class="notes-input" placeholder="notes (optional)" />
        </div>
      </div>`;
    })
    .join("");

  el.querySelectorAll(".card").forEach((card) => {
    const qid = Number(card.dataset.qid);
    card.querySelectorAll("[data-mark]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const notes = card.querySelector(".notes-input").value;
        onMarkQuestion(qid, btn.dataset.mark, notes);
      });
    });
  });
}

async function onMarkQuestion(id, result, notes) {
  try {
    const res = await api.post(`/api/questions/${id}/mark`, { result, notes: notes || null });
    if (res.round1_just_completed) {
      const banner = document.getElementById("congrats-banner");
      banner.classList.remove("hidden");
      banner.addEventListener("click", () => banner.classList.add("hidden"), { once: true });
    }
    await Promise.all([loadToday(), loadProgressAndTopics(), loadState()]);
  } catch (e) {
    alert(e.message);
  }
}

async function onRegenerate() {
  await api.post("/api/today/regenerate");
  await loadToday();
}

// ------------------------------------------------------------ progress

async function loadProgressAndTopics() {
  const data = await api.get("/api/progress");
  currentTopics = data.topics;
  renderProgress(data);
  renderTopicManager(data.topics);
  renderEditorTopicSelect(data.topics);
}

function renderProgress(data) {
  const o = data.overall;
  document.getElementById("overall-progress").innerHTML = `
    <div class="overall-stat">
      <div class="label">Round 1 (Pen & Paper)</div>
      <div class="value">${o.round1_pct}%</div>
      <div class="bar-label">${o.round1_done}/${o.round1_total} graduated</div>
    </div>
    <div class="overall-stat">
      <div class="label">Round 2 (Implementation)</div>
      <div class="value">${o.round2_pct}%</div>
      <div class="bar-label">${o.round2_done}/${o.round2_total} graduated</div>
    </div>
  `;

  document.getElementById("progress-list").innerHTML = data.topics
    .map((t) => {
      const r1pct = t.total_questions ? Math.round((100 * t.round1_done) / t.total_questions) : 0;
      const r2pct = t.total_questions ? Math.round((100 * t.round2_done) / t.total_questions) : 0;
      return `
      <div class="progress-row">
        <div class="progress-row-top">
          <span class="progress-row-name">${escapeHtml(t.name)}</span>
          <span class="status-pill">${t.status}</span>
        </div>
        <div class="bar-label">Round 1: ${t.round1_done}/${t.total_questions}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${r1pct}%"></div></div>
        <div class="bar-label">Round 2: ${t.round2_done}/${t.total_questions}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${r2pct}%"></div></div>
      </div>`;
    })
    .join("");
}

// -------------------------------------------------------- topic manager

function renderTopicManager(topics) {
  const byStatus = { active: [], pending: [], locked: [], done: [] };
  topics.forEach((t) => byStatus[t.status]?.push(t));

  const isWeekend = currentState?.is_weekend;

  document.getElementById("topics-active").innerHTML =
    byStatus.active.map((t) => topicChip(t, `<div class="sub">${t.round1_done}/${t.total_questions} R1 · ${t.round2_done}/${t.total_questions} R2</div>`)).join("") ||
    emptyNote();

  document.getElementById("topics-pending").innerHTML =
    byStatus.pending
      .map((t) =>
        topicChip(
          t,
          `<div class="sub">started ${t.started_at || "?"}</div>
           <button class="btn btn-sm btn-primary" data-confirm="${t.id}">Confirm first pass done</button>`
        )
      )
      .join("") || emptyNote();

  document.getElementById("topics-locked").innerHTML =
    byStatus.locked
      .map((t) =>
        topicChip(
          t,
          `${t.note ? `<div class="sub">${escapeHtml(t.note)}</div>` : ""}
           <button class="btn btn-sm btn-primary" data-unlock="${t.id}" ${isWeekend ? "" : "disabled"}>
             ${isWeekend ? "Unlock this weekend" : "Unlock (weekends only)"}
           </button>`
        )
      )
      .join("") || emptyNote();

  document.getElementById("topics-done").innerHTML =
    byStatus.done.map((t) => topicChip(t, `<div class="sub">Fully graduated 🎓</div>`)).join("") || emptyNote();

  document.querySelectorAll("[data-unlock]").forEach((b) =>
    b.addEventListener("click", () => onUnlockTopic(Number(b.dataset.unlock)))
  );
  document.querySelectorAll("[data-confirm]").forEach((b) =>
    b.addEventListener("click", () => onConfirmFirstPass(Number(b.dataset.confirm)))
  );
}

function topicChip(t, innerExtra) {
  return `<div class="topic-chip"><div class="name">${escapeHtml(t.name)}</div>${innerExtra}</div>`;
}

function emptyNote() {
  return `<div class="empty-note">none</div>`;
}

async function onUnlockTopic(id) {
  try {
    await api.post(`/api/topics/${id}/unlock`);
    await Promise.all([loadState(), loadProgressAndTopics()]);
  } catch (e) {
    alert(e.message);
  }
}

async function onConfirmFirstPass(id) {
  try {
    await api.post(`/api/topics/${id}/confirm-first-pass`);
    await Promise.all([loadState(), loadProgressAndTopics(), loadToday()]);
  } catch (e) {
    alert(e.message);
  }
}

async function onAddTopic(ev) {
  ev.preventDefault();
  const name = document.getElementById("new-topic-name").value.trim();
  const note = document.getElementById("new-topic-note").value.trim() || null;
  const status = document.getElementById("new-topic-status").value;
  if (!name) return;
  await api.post("/api/topics", { name, note, status });
  document.getElementById("add-topic-form").reset();
  await loadProgressAndTopics();
}

// ---------------------------------------------------------------- editor

function renderEditorTopicSelect(topics) {
  const select = document.getElementById("editor-topic-select");
  const prev = select.value;
  select.innerHTML = topics.map((t) => `<option value="${t.id}">${escapeHtml(t.name)} (${t.status})</option>`).join("");
  if (prev && topics.some((t) => String(t.id) === prev)) {
    select.value = prev;
  }
  loadEditorQuestions();
}

function onEditorTopicChange() {
  loadEditorQuestions();
}

async function loadEditorQuestions() {
  const select = document.getElementById("editor-topic-select");
  const topicId = select.value;
  if (!topicId) {
    document.getElementById("editor-question-list").innerHTML = emptyNote();
    return;
  }
  const questions = await api.get(`/api/questions?topic_id=${topicId}`);
  renderEditorQuestions(questions);
}

function renderEditorQuestions(questions) {
  const el = document.getElementById("editor-question-list");
  if (!questions.length) {
    el.innerHTML = `<div class="empty-note">No questions in this topic yet.</div>`;
    return;
  }
  el.innerHTML = questions
    .map(
      (q) => `
    <div class="card" data-qid="${q.id}">
      <div class="q-edit-row">
        <input type="text" class="edit-title" value="${escapeAttr(q.title)}" style="flex:2 1 200px" />
        <input type="url" class="edit-url" value="${escapeAttr(q.url || "")}" placeholder="URL" style="flex:2 1 200px" />
        <input type="text" class="edit-difficulty" value="${escapeAttr(q.difficulty || "")}" placeholder="Difficulty" style="flex:1 1 100px" />
        <button class="btn btn-sm btn-primary" data-save>Save</button>
        <button class="btn btn-sm btn-failed" data-delete>Delete</button>
      </div>
      <div class="q-meta" style="margin-top:6px;">
        <span>R1: ${q.round1_status}</span>
        <span>R2: ${q.round2_status}</span>
        <span>streak ${q.streak_stage}</span>
        <span>fails ${q.fail_count}</span>
        <span>next due ${q.next_due_date || "-"}</span>
      </div>
    </div>`
    )
    .join("");

  el.querySelectorAll(".card").forEach((card) => {
    const qid = Number(card.dataset.qid);
    card.querySelector("[data-save]").addEventListener("click", async () => {
      const title = card.querySelector(".edit-title").value.trim();
      const url = card.querySelector(".edit-url").value.trim() || null;
      const difficulty = card.querySelector(".edit-difficulty").value.trim() || null;
      try {
        await api.put(`/api/questions/${qid}`, { title, url, difficulty });
        await Promise.all([loadEditorQuestions(), loadToday(), loadProgressAndTopics()]);
      } catch (e) {
        alert(e.message);
      }
    });
    card.querySelector("[data-delete]").addEventListener("click", async () => {
      if (!confirm("Delete this question?")) return;
      await api.del(`/api/questions/${qid}`);
      await Promise.all([loadEditorQuestions(), loadToday(), loadProgressAndTopics()]);
    });
  });
}

async function onAddQuestion(ev) {
  ev.preventDefault();
  const topicId = Number(document.getElementById("editor-topic-select").value);
  const title = document.getElementById("new-question-title").value.trim();
  const url = document.getElementById("new-question-url").value.trim() || null;
  const difficulty = document.getElementById("new-question-difficulty").value.trim() || null;
  if (!topicId || !title) return;
  await api.post("/api/questions", { topic_id: topicId, title, url, difficulty });
  document.getElementById("add-question-form").reset();
  await Promise.all([loadEditorQuestions(), loadProgressAndTopics()]);
}

// ----------------------------------------------------------------- util

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) {
  return escapeHtml(s);
}
