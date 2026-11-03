(function () {
  const LABELS = ["positive", "neutral", "negative", "sarcastic"];
  const PAGE_SIZE = 50;
  const $ = (id) => document.getElementById(id);
  const pct = (x, digits = 2) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);

  let data = null;
  let page = 0;
  let sort = { key: "id", dir: -1 };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function tag(label) {
    return label ? el("span", `tag ${label}`, label) : el("span", "muted", "—");
  }

  function renderTiles() {
    const s = data.summary;
    const tiles = [
      ["Total records", s.total_records.toLocaleString()],
      ["Unique texts", s.unique_texts],
      ["Annotated here", s.ui_records],
      ["Average agreement", pct(s.average_agreement)],
      ["Full agreement", s.total_records ? pct(s.full_agreement / s.total_records, 1) : "—"],
      ["Classifier accuracy", pct(s.classifier_accuracy)],
    ];
    $("tiles").innerHTML = "";
    tiles.forEach(([label, value]) => {
      const tile = el("div", "tile");
      tile.append(el("div", "tile-label", label), el("div", "tile-value", String(value)));
      tile.dataset.tile = label;
      $("tiles").appendChild(tile);
    });
  }

  function renderClassifier() {
    const c = data.classifier;
    if (!c) {
      $("report").textContent = "No classifier run yet — save at least 10 annotations, then rerun.";
      $("run-meta").textContent = "";
      $("report-scope").textContent = "";
    } else {
      $("report").textContent = c.report_text;
      $("report-scope").textContent = `(test set, ${c.n_test} records)`;
      $("split").value = c.split;
      const when = new Date(c.created_at).toLocaleString();
      $("run-meta").innerHTML = "";
      $("run-meta").append(
        `Run #${c.id} · ${when} · seed ${c.seed} · trained on ${c.n_train}, tested on ${c.n_test} of ${c.n_records} records. `
      );
      if (c.new_since_run > 0) {
        $("run-meta").appendChild(el("span", "stale", `${c.new_since_run} new annotation${c.new_since_run === 1 ? "" : "s"} since this run — rerun to include them.`));
      }
    }
    $("history").innerHTML = "";
    data.history.forEach((run) => {
      const tr = el("tr");
      tr.append(
        el("td", "num", `#${run.id}`),
        el("td", "", run.split === "sentences" ? "sentences" : "records"),
        el("td", "num", run.seed),
        el("td", "num", run.n_records),
        el("td", "num", pct(run.accuracy))
      );
      $("history").appendChild(tr);
    });
  }

  function filteredRecords() {
    const q = $("search").value.trim().toLowerCase();
    const source = $("source").value;
    const disagree = $("only-disagree").checked;
    const miss = $("only-miss").checked;
    const rows = data.records.filter(
      (r) =>
        (!q || r.text.toLowerCase().includes(q)) &&
        (!source || r.source === source) &&
        (!disagree || r.agreement < 1) &&
        (!miss || (r.prediction && r.prediction !== r.resolved))
    );
    const { key, dir } = sort;
    return rows.sort((a, b) => {
      const x = a[key] ?? "";
      const y = b[key] ?? "";
      return (x < y ? -1 : x > y ? 1 : 0) * dir || (a.id - b.id) * dir;
    });
  }

  function renderRecords() {
    const rows = filteredRecords();
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    page = Math.min(page, pages - 1);
    const tbody = $("records");
    tbody.innerHTML = "";
    rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).forEach((r) => {
      const tr = el("tr");
      tr.dataset.id = r.id;
      const pred = el("td");
      pred.appendChild(tag(r.prediction));
      if (r.prediction && r.prediction !== r.resolved) pred.appendChild(el("span", "miss", " ✕"));
      const resolved = el("td");
      resolved.appendChild(tag(r.resolved));
      tr.append(
        el("td", "num", r.id),
        el("td", "text", r.text),
        ...r.annotations.map((a) => el("td", "", a)),
        resolved,
        pred,
        el("td", "num", r.confidence == null ? "—" : pct(r.confidence)),
        el("td", "num", pct(r.agreement)),
        el("td", "muted", r.source === "ui" ? "annotated here" : "dataset")
      );
      tbody.appendChild(tr);
    });
    $("page-info").textContent = rows.length
      ? `${page * PAGE_SIZE + 1}–${Math.min(rows.length, (page + 1) * PAGE_SIZE)} of ${rows.length}`
      : "No matching records";
    $("prev-page").disabled = page === 0;
    $("next-page").disabled = page >= pages - 1;
    document.querySelectorAll("th[data-sort]").forEach((th) => {
      th.setAttribute("aria-sort", th.dataset.sort === sort.key ? (sort.dir > 0 ? "ascending" : "descending") : "none");
    });
  }

  function renderSentences() {
    $("legend").innerHTML = LABELS.map((l) => `<span><i style="background:var(--${l})"></i>${l}</span>`).join("");
    const tbody = $("sentences");
    tbody.innerHTML = "";
    data.sentences.forEach((s) => {
      const total = Object.values(s.votes).reduce((a, b) => a + b, 0) || 1;
      const bar = el("div", "votebar");
      bar.title = LABELS.map((l) => `${l}: ${s.votes[l]}`).join(", ");
      LABELS.forEach((l) => {
        if (!s.votes[l]) return;
        const seg = el("span", l);
        seg.style.width = `${(s.votes[l] / total) * 100}%`;
        bar.appendChild(seg);
      });
      const barCell = el("td");
      barCell.appendChild(bar);
      const resolved = el("td");
      resolved.appendChild(tag(s.resolved));
      const tr = el("tr");
      tr.append(el("td", "text", s.text), el("td", "num", s.records), barCell, resolved,
        el("td", "num", pct(s.agreement)), el("td", "num", pct(s.record_agreement)));
      tbody.appendChild(tr);
    });
  }

  function renderAll() {
    renderTiles();
    renderClassifier();
    renderRecords();
    renderSentences();
  }

  async function load() {
    const res = await fetch("/api/stats");
    data = await res.json();
    renderAll();
  }

  $("rerun").addEventListener("click", async () => {
    const btn = $("rerun");
    btn.disabled = true;
    btn.textContent = "Training…";
    $("run-error").textContent = "";
    try {
      const res = await fetch("/api/classifier/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ split: $("split").value }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || "Training failed.");
      await load();
    } catch (e) {
      $("run-error").textContent = e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Rerun classifier";
    }
  });

  ["search", "source", "only-disagree", "only-miss"].forEach((id) =>
    $(id).addEventListener("input", () => {
      page = 0;
      renderRecords();
    })
  );
  $("prev-page").addEventListener("click", () => { page -= 1; renderRecords(); });
  $("next-page").addEventListener("click", () => { page += 1; renderRecords(); });
  document.querySelectorAll("th[data-sort]").forEach((th) =>
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      sort = { key, dir: sort.key === key ? -sort.dir : key === "text" ? 1 : -1 };
      renderRecords();
    })
  );

  const tabs = { records: $("tab-records"), sentences: $("tab-sentences") };
  Object.entries(tabs).forEach(([name, btn]) =>
    btn.addEventListener("click", () => {
      Object.entries(tabs).forEach(([other, b]) => {
        b.setAttribute("aria-selected", String(other === name));
        $(`view-${other}`).hidden = other !== name;
      });
    })
  );

  load().catch(() => { $("report").textContent = "Could not load stats."; });
})();
