(function () {
  const list = document.getElementById("favorites");
  const empty = document.getElementById("empty");
  const loading = document.getElementById("loading");
  const filterEl = document.getElementById("mood-filter");
  const errorEl = document.getElementById("error");

  /** @type {any[]} */
  let favorites = [];
  /** @type {string | null} */
  let filter = null;

  const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  }

  async function api(url, options = {}) {
    const res = await fetch(url, { credentials: "same-origin", ...options });
    if (res.status === 401) {
      location.href = MoodSession.loginUrl();
      throw new Error("Please log in.");
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request failed.");
    return body;
  }

  function renderFilter() {
    const labels = new Map();
    favorites.forEach((f) => f.moods.forEach((m) => labels.set(m.key, m.label)));
    if (filter && !labels.has(filter)) filter = null;
    filterEl.innerHTML = "";
    filterEl.classList.toggle("hidden", labels.size < 2);
    filterEl.classList.toggle("flex", labels.size >= 2);
    const chip = (key, label) => {
      const btn = el("button", "", label);
      btn.type = "button";
      btn.dataset.filter = key ?? "";
      const active = filter === key;
      btn.className = active
        ? "rounded-full border border-orange-300 bg-orange-100 px-3 py-1.5 text-sm font-medium text-orange-800 ring-2 ring-orange-500"
        : "rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:border-orange-300 hover:bg-orange-50";
      btn.addEventListener("click", () => {
        filter = key;
        render();
      });
      filterEl.appendChild(btn);
    };
    chip(null, "All");
    [...labels.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([key, label]) => chip(key, label));
  }

  function recipeDetails(fav) {
    const details = el("details", "mt-3");
    details.appendChild(el("summary", "cursor-pointer text-sm font-medium text-slate-600 hover:text-slate-900", "Show recipe"));
    if (fav.ingredients.length) {
      const ul = el("ul", "mt-2 list-inside list-disc space-y-0.5 text-sm text-slate-700");
      fav.ingredients.forEach((row) => ul.appendChild(el("li", "", `${row.measure ? `${row.measure} ` : ""}${row.ingredient}`)));
      details.appendChild(ul);
    }
    details.appendChild(
      el("p", "mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700", (fav.instructions || "No instructions listed.").trim())
    );
    return details;
  }

  function card(fav) {
    const li = el("li", "rounded-2xl border border-white/60 bg-white/80 p-4 shadow-sm backdrop-blur");
    li.dataset.favoriteId = String(fav.id);
    const row = el("div", "flex gap-4");

    const img = el("img", "h-24 w-32 shrink-0 rounded-xl bg-slate-100 object-cover sm:h-28 sm:w-40");
    img.src = fav.image || "";
    img.alt = `Photo of ${fav.name}`;
    img.loading = "lazy";
    row.appendChild(img);

    const body = el("div", "min-w-0 flex-1");
    body.appendChild(el("h2", "font-display text-lg font-semibold text-slate-900", fav.name));
    const meta = [fav.category, fav.area].filter(Boolean).join(" · ");
    if (meta) body.appendChild(el("p", "text-xs text-slate-500", meta));

    const moods = el("ul", "mt-2 space-y-1");
    fav.moods.forEach((m) => {
      const item = el("li", "flex flex-wrap items-baseline gap-x-2 text-sm");
      const label = el("span", "text-slate-600", "Mood: ");
      label.appendChild(el("strong", "text-slate-900", m.label));
      item.appendChild(label);
      item.appendChild(el("span", "text-xs text-slate-400", `Saved ${dateFmt.format(new Date(m.saved_at))}`));
      if (fav.moods.length > 1) {
        const untag = el("button", "text-xs text-slate-400 hover:text-red-600", "✕");
        untag.type = "button";
        untag.setAttribute("aria-label", `Remove mood ${m.label} from ${fav.name}`);
        untag.addEventListener("click", () => removeMood(fav, m));
        item.appendChild(untag);
      }
      moods.appendChild(item);
    });
    body.appendChild(moods);

    const actions = el("div", "mt-2 flex flex-wrap gap-3 text-sm");
    if (fav.youtube) {
      const a = el("a", "font-medium text-orange-700 underline hover:text-orange-900", "Video");
      a.href = fav.youtube;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      actions.appendChild(a);
    }
    if (fav.source) {
      const a = el("a", "font-medium text-orange-700 underline hover:text-orange-900", "Source");
      a.href = fav.source;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      actions.appendChild(a);
    }
    const remove = el("button", "font-medium text-red-700 hover:text-red-900", "Remove");
    remove.type = "button";
    remove.dataset.remove = String(fav.id);
    remove.addEventListener("click", () => removeFavorite(fav));
    actions.appendChild(remove);
    body.appendChild(actions);

    row.appendChild(body);
    li.appendChild(row);
    li.appendChild(recipeDetails(fav));
    return li;
  }

  function render() {
    renderFilter();
    list.innerHTML = "";
    const shown = filter ? favorites.filter((f) => f.moods.some((m) => m.key === filter)) : favorites;
    shown.forEach((f) => list.appendChild(card(f)));
    empty.classList.toggle("hidden", favorites.length > 0);
  }

  async function removeFavorite(fav) {
    try {
      await api(`/api/favorites/${fav.id}`, { method: "DELETE" });
      favorites = favorites.filter((f) => f.id !== fav.id);
      render();
    } catch (e) {
      showError(e.message);
    }
  }

  async function removeMood(fav, mood) {
    try {
      await api(`/api/favorites/${fav.id}/moods/${encodeURIComponent(mood.key)}`, { method: "DELETE" });
      fav.moods = fav.moods.filter((m) => m.key !== mood.key);
      render();
    } catch (e) {
      showError(e.message);
    }
  }

  (async () => {
    const user = await MoodSession.load();
    if (!user) {
      location.replace(MoodSession.loginUrl());
      return;
    }
    MoodSession.renderNav("favorites");
    try {
      favorites = (await api("/api/favorites")).favorites;
      render();
    } catch (e) {
      showError(e.message);
    } finally {
      loading.classList.add("hidden");
    }
  })();
})();
