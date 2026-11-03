(function () {
  const STORAGE_KEY = "moodRecipesExcluded";

  /** @type {{key: string, label: string, custom: boolean, id?: number}[]} */
  let moods = [];

  /** @type {string | null} */
  let selectedMood = null;

  const moodButtons = document.getElementById("mood-buttons");
  const recipeSection = document.getElementById("recipe-section");
  const recipeLoading = document.getElementById("recipe-loading");
  const recipeContent = document.getElementById("recipe-content");
  const recipeImage = document.getElementById("recipe-image");
  const recipeTitle = document.getElementById("recipe-title");
  const recipeMeta = document.getElementById("recipe-meta");
  const recipeIngredients = document.getElementById("recipe-ingredients");
  const recipeInstructions = document.getElementById("recipe-instructions");
  const recipeYoutube = document.getElementById("recipe-youtube");
  const btnAnother = document.getElementById("btn-another");
  const btnSave = document.getElementById("btn-save");
  const errorEl = document.getElementById("error");
  const addMoodSection = document.getElementById("add-mood");
  const addMoodForm = document.getElementById("add-mood-form");
  const addMoodMsg = document.getElementById("add-mood-msg");
  const moodBase = document.getElementById("mood-base");
  const moodFocus = document.getElementById("mood-focus");

  function loadExcluded() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return typeof parsed === "object" && parsed !== null ? parsed : {};
    } catch {
      return {};
    }
  }

  function saveExcluded(map) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
    } catch {}
  }

  function getExcludedForMood(mood) {
    const map = loadExcluded();
    const list = map[mood];
    return Array.isArray(list) ? list : [];
  }

  function addExcluded(mood, id) {
    const map = loadExcluded();
    const cur = Array.isArray(map[mood]) ? map[mood] : [];
    if (!cur.includes(id)) cur.push(id);
    map[mood] = cur;
    saveExcluded(map);
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("hidden");
  }

  function setLoading(loading) {
    recipeSection.classList.remove("hidden");
    if (loading) {
      recipeLoading.classList.remove("hidden");
      recipeContent.classList.add("hidden");
    } else {
      recipeLoading.classList.add("hidden");
      recipeContent.classList.remove("hidden");
    }
  }

  function errorDetail(body, fallback) {
    let detail = body.detail ?? body.error;
    if (Array.isArray(detail)) detail = detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")).join(" ");
    if (typeof detail === "object" && detail !== null) detail = JSON.stringify(detail);
    return typeof detail === "string" && detail ? detail : fallback;
  }

  function renderRecipe(data) {
    if (data.id) recipeImage.dataset.mealId = String(data.id);
    recipeImage.src = data.image || "";
    recipeImage.alt = data.name ? `Photo of ${data.name}` : "Recipe";
    recipeTitle.textContent = data.name || "Recipe";
    const parts = [];
    if (data.category) parts.push(data.category);
    if (data.area) parts.push(data.area);
    recipeMeta.textContent = parts.join(" · ");

    recipeIngredients.innerHTML = "";
    if (Array.isArray(data.ingredients) && data.ingredients.length) {
      const ul = document.createElement("ul");
      ul.className = "list-inside list-disc space-y-1 text-sm text-slate-700";
      data.ingredients.forEach((row) => {
        const li = document.createElement("li");
        const m = row.measure ? `${row.measure} ` : "";
        li.textContent = `${m}${row.ingredient}`.trim();
        ul.appendChild(li);
      });
      const h4 = document.createElement("h4");
      h4.className = "mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500";
      h4.textContent = "Ingredients";
      recipeIngredients.appendChild(h4);
      recipeIngredients.appendChild(ul);
    }

    const instr = data.instructions || "";
    recipeInstructions.textContent = instr.trim() || "No instructions listed.";

    if (data.youtube && String(data.youtube).trim()) {
      recipeYoutube.href = data.youtube;
      recipeYoutube.classList.remove("hidden");
    } else {
      recipeYoutube.classList.add("hidden");
    }
    refreshSaveButton(data.id);
  }

  // ---- favorites ----

  function setSaveButton(saved) {
    btnSave.disabled = saved;
    btnSave.textContent = saved ? "♥ Saved for this mood" : "♡ Save to favorites";
  }

  async function refreshSaveButton(mealId) {
    setSaveButton(false);
    if (!MoodSession.user || !mealId) return;
    const res = await fetch(`/api/favorites/status?meal_id=${encodeURIComponent(mealId)}`, { credentials: "same-origin" });
    if (!res.ok) return;
    const body = await res.json();
    if (recipeImage.dataset.mealId === String(mealId)) setSaveButton(body.moods.includes(selectedMood));
  }

  btnSave.addEventListener("click", async () => {
    if (!MoodSession.user) {
      location.href = MoodSession.loginUrl();
      return;
    }
    const mealId = recipeImage.dataset.mealId;
    if (!mealId || !selectedMood) return;
    btnSave.disabled = true;
    const res = await fetch("/api/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ meal_id: mealId, mood: selectedMood }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      btnSave.disabled = false;
      showError(errorDetail(body, "Could not save this recipe."));
      return;
    }
    setSaveButton(true);
  });

  async function fetchRecipe(excludeList) {
    if (!selectedMood) return;
    clearError();
    setLoading(true);

    const params = new URLSearchParams({ mood: selectedMood });
    if (excludeList.length) params.set("exclude", excludeList.join(","));

    const res = await fetch(`/api/recipe?${params.toString()}`, { credentials: "same-origin" });
    const body = await res.json().catch(() => ({}));

    if (!res.ok) throw new Error(errorDetail(body, "Could not load recipe."));

    return body;
  }

  async function loadRecipe(excludeList) {
    try {
      const data = await fetchRecipe(excludeList);
      renderRecipe(data);
      setLoading(false);
    } catch (e) {
      setLoading(false);
      recipeContent.classList.add("hidden");
      showError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }

  // ---- moods ----

  const moodBtnClass =
    "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-orange-300 hover:bg-orange-50 focus:outline-none focus:ring-2 focus:ring-orange-400";
  const selectedClasses = ["ring-2", "ring-orange-500", "bg-orange-100", "border-orange-300"];

  function selectMood(key) {
    selectedMood = key;
    document.querySelectorAll("#mood-buttons button[data-mood]").forEach((b) => {
      b.classList.toggle("selected", b.dataset.mood === key);
      selectedClasses.forEach((c) => b.classList.toggle(c, b.dataset.mood === key));
    });
    loadRecipe(getExcludedForMood(key));
  }

  function renderMoods() {
    moodButtons.innerHTML = "";
    const sorted = [...moods].sort((a, b) => a.label.localeCompare(b.label));
    sorted.forEach((m) => {
      const wrap = document.createElement("span");
      wrap.className = "inline-flex items-center";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.mood = m.key;
      btn.textContent = m.label;
      btn.className = moodBtnClass;
      if (m.custom) {
        btn.title = m.focus
          ? `Your mood · ${m.focus.value}, then ${m.base_label}`
          : `Your mood · based on ${m.base_label}`;
        btn.classList.add("border-dashed", "border-orange-300");
      }
      if (m.key === selectedMood) selectedClasses.forEach((c) => btn.classList.add(c));
      btn.addEventListener("click", () => selectMood(m.key));
      wrap.appendChild(btn);

      if (m.custom) {
        const del = document.createElement("button");
        del.type = "button";
        del.className = "-ml-2 h-6 w-6 rounded-full bg-white text-xs text-slate-400 shadow hover:bg-red-50 hover:text-red-600";
        del.setAttribute("aria-label", `Delete mood ${m.label}`);
        del.dataset.deleteMood = String(m.id);
        del.textContent = "✕";
        del.addEventListener("click", () => deleteMood(m));
        wrap.appendChild(del);
      }
      moodButtons.appendChild(wrap);
    });
  }

  function fillMoodForm(builtin, focusOptions) {
    moodBase.innerHTML = "";
    builtin.forEach((m) => moodBase.add(new Option(m.label, m.key)));
    const addGroup = (label, type, values) => {
      const group = document.createElement("optgroup");
      group.label = label;
      values.forEach((v) => group.appendChild(new Option(v, `${type}:${v}`)));
      moodFocus.appendChild(group);
    };
    addGroup("Category", "c", focusOptions.categories);
    addGroup("Cuisine", "a", focusOptions.areas);
  }

  async function loadMoods(firstLoad) {
    const res = await fetch("/api/moods", { credentials: "same-origin" });
    const body = await res.json();
    moods = [...body.builtin, ...body.custom];
    if (firstLoad) fillMoodForm(body.builtin, body.focus_options);
    renderMoods();
  }

  function moodMessage(text, ok) {
    addMoodMsg.textContent = text;
    addMoodMsg.className = `mt-2 text-sm ${ok ? "text-emerald-700" : "text-red-700"}`;
  }

  addMoodForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const label = document.getElementById("mood-label").value.trim();
    if (!label) return moodMessage("Give your mood a name.", false);
    const [focusType, ...rest] = moodFocus.value ? moodFocus.value.split(":") : [null];
    const res = await fetch("/api/moods", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        label,
        base_mood: moodBase.value,
        focus_type: focusType,
        focus_value: rest.join(":") || null,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return moodMessage(errorDetail(body, "Could not add mood."), false);
    document.getElementById("mood-label").value = "";
    moodFocus.value = "";
    moodMessage(`Added “${body.label}”.`, true);
    await loadMoods(false);
    selectMood(body.key);
  });

  async function deleteMood(m) {
    const res = await fetch(`/api/moods/${m.id}`, { method: "DELETE", credentials: "same-origin" });
    if (!res.ok) return moodMessage("Could not delete mood.", false);
    if (selectedMood === m.key) {
      selectedMood = null;
      recipeSection.classList.add("hidden");
    }
    moodMessage(`Deleted “${m.label}”.`, true);
    await loadMoods(false);
  }

  btnAnother.addEventListener("click", () => {
    if (!selectedMood) return;
    const currentId = recipeImage.dataset.mealId;
    if (currentId) addExcluded(selectedMood, currentId);
    loadRecipe(getExcludedForMood(selectedMood));
  });

  (async () => {
    const user = await MoodSession.load();
    MoodSession.renderNav("home");
    if (user) addMoodSection.classList.remove("hidden");
    else {
      document.getElementById("login-hint-link").href = MoodSession.loginUrl();
      document.getElementById("login-hint").classList.remove("hidden");
    }
    try {
      await loadMoods(true);
    } catch {
      showError("Could not load moods.");
    }
  })();
})();
