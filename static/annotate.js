(function () {
  const LABELS = ["positive", "neutral", "negative", "sarcastic"];
  const ANNOTATORS = 3;
  const title = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const pct = (x) => `${Math.round(x * 100)}%`;

  const sentenceEl = document.getElementById("sentence");
  const metaEl = document.getElementById("sentence-meta");
  const annotatorsEl = document.getElementById("annotators");
  const saveBtn = document.getElementById("save");
  const nextBtn = document.getElementById("next");
  const statusEl = document.getElementById("status");
  const countEl = document.getElementById("session-count");

  let sentence = null; // { id, text, times_annotated }
  let choices = Array(ANNOTATORS).fill(null);
  let clientKey = null; // one key per drawn sentence, so a double click can't save twice
  let saved = false;
  let sessionSaved = 0;

  const newKey = () =>
    (crypto.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  function setStatus(text, kind = "") {
    statusEl.textContent = text;
    statusEl.className = `status ${kind}`;
  }

  function buildAnnotators() {
    for (let a = 0; a < ANNOTATORS; a++) {
      const row = document.createElement("div");
      row.className = "annotator";
      const name = document.createElement("div");
      name.className = "annotator-name";
      name.id = `annotator-${a + 1}-label`;
      name.textContent = `Annotator ${a + 1}`;
      const group = document.createElement("div");
      group.className = "choices";
      group.setAttribute("role", "radiogroup");
      group.setAttribute("aria-labelledby", name.id);
      LABELS.forEach((label) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "choice";
        btn.dataset.annotator = String(a);
        btn.dataset.label = label;
        btn.setAttribute("role", "radio");
        btn.setAttribute("aria-checked", "false");
        btn.textContent = title(label);
        btn.addEventListener("click", () => choose(a, label));
        group.appendChild(btn);
      });
      row.append(name, group);
      annotatorsEl.appendChild(row);
    }
  }

  function render() {
    document.querySelectorAll(".choice").forEach((btn) => {
      const a = Number(btn.dataset.annotator);
      btn.setAttribute("aria-checked", String(choices[a] === btn.dataset.label));
      btn.disabled = saved || !sentence;
    });
    const chosen = choices.filter(Boolean).length;
    saveBtn.disabled = saved || !sentence || chosen < ANNOTATORS;
    saveBtn.textContent = saved ? "Saved ✓" : "Save annotation";
    if (!saved && sentence) {
      setStatus(chosen < ANNOTATORS ? `Choose a label for every annotator (${chosen} of ${ANNOTATORS} chosen).` : "Ready to save.");
    }
    countEl.textContent = sessionSaved ? `Saved this session: ${sessionSaved}` : "";
  }

  function choose(annotator, label) {
    if (saved) return;
    choices[annotator] = label;
    render();
  }

  async function loadSentence() {
    nextBtn.disabled = true;
    try {
      const params = sentence ? `?exclude=${sentence.id}` : "";
      const res = await fetch(`/api/sentence/random${params}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Could not load a sentence.");
      sentence = body;
      choices = Array(ANNOTATORS).fill(null);
      clientKey = newKey();
      saved = false;
      sentenceEl.textContent = sentence.text;
      metaEl.textContent = `Sentence #${sentence.id} · annotated ${sentence.times_annotated} time${sentence.times_annotated === 1 ? "" : "s"} so far`;
      render();
    } catch (e) {
      sentenceEl.textContent = "—";
      setStatus(e.message, "error");
    } finally {
      nextBtn.disabled = false;
    }
  }

  async function save() {
    if (saveBtn.disabled) return;
    saveBtn.disabled = true;
    try {
      const res = await fetch("/api/annotations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sentence_id: sentence.id, labels: choices, client_key: clientKey }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join(" ") : body.detail;
        throw new Error(detail || "Could not save.");
      }
      saved = true;
      sessionSaved += 1;
      render();
      setStatus(`Saved as record #${body.id} — resolved ${body.resolved}, agreement ${pct(body.agreement)}. Generate the next sentence to continue.`, "ok");
      nextBtn.focus();
    } catch (e) {
      render();
      setStatus(e.message, "error");
    }
  }

  saveBtn.addEventListener("click", save);
  nextBtn.addEventListener("click", loadSentence);

  buildAnnotators();
  render();
  loadSentence();
})();
