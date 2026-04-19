// ══════════════════════════════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════════════════════════════
const state = {
  step: 1,
  cuisines: [],
  sourceCuisine: null,
  dishGroups: [],      // [{course, dishes}]
  allDishes: [],       // flat list
  favoriteDishes: [],
  targetCuisines: [],
  tastePrefs: {
    dietary: "any",
    spice_level: "medium",
    likes_creamy: false,
    likes_aromatic: false,
    likes_sweet: false,
    likes_sour: false,
    allowed_proteins: "any",  // "any" or array like ["chicken","fish"]
    prefer_vegetarian: false, // soft re-rank: float veg dishes above meat
  },
  results: null,
  engine: "algorithm",  // "algorithm" or "llm"
};

const FLAGS = {
  American:"🇺🇸",Brazilian:"🇧🇷",Chinese:"🇨🇳",Colombian:"🇨🇴",Croatian:"🇭🇷",
  French:"🇫🇷",Georgian:"🇬🇪",Greek:"🇬🇷",Hungarian:"🇭🇺",Indian:"🇮🇳",
  Indonesian:"🇮🇩",Italian:"🇮🇹",Japanese:"🇯🇵",Korean:"🇰🇷",Lebanese:"🇱🇧",
  Mexican:"🇲🇽",Peruvian:"🇵🇪",Polish:"🇵🇱",Portuguese:"🇵🇹",Serbian:"🇷🇸",
  Spanish:"🇪🇸",Thai:"🇹🇭",Turkish:"🇹🇷",Vietnamese:"🇻🇳",
};

const COURSE_ICONS = {
  "Appetizer": "🥗", "Soup": "🍲", "Salad": "🥬", "Main Course": "🍛",
  "Dessert": "🍮", "Drink": "🥤",
  // Legacy names (fallback)
  "Appetizers": "🥗", "Soups": "🍲", "Salads": "🥬", "Entrees": "🍛",
  "Sides & Breads": "🍞", "Snacks & Street Food": "🥟", "Breakfast": "🍳", "Desserts": "🍮", "Drinks": "🥤",
};

// Natural meal-progression order used to sort courses consistently across all engines.
const COURSE_ORDER = [
  "Appetizer", "Appetizers",
  "Soup", "Soups",
  "Salad", "Salads",
  "Breakfast",
  "Snacks & Street Food",
  "Main Course", "Entrees",
  "Sides & Breads",
  "Dessert", "Desserts",
  "Drink", "Drinks",
];
function courseRank(name) {
  const i = COURSE_ORDER.indexOf(name);
  return i === -1 ? 999 : i;
}
function sortedCourseEntries(courses) {
  return Object.entries(courses || {}).sort(
    ([a], [b]) => courseRank(a) - courseRank(b)
  );
}

// ─ Show-more helpers ─────────────────────────────────────────────────────
// Split a course's dish list into "visible by default" and "hidden behind
// Show more". The server sets info.visible_per_course (default 3).
function splitVisibleHidden(dishes, visiblePerCourse) {
  const N = Math.max(1, visiblePerCourse || 3);
  return {
    visible: dishes.slice(0, N),
    hidden:  dishes.slice(N),
  };
}

// Render "Because you liked …" line. If the dish was matched by multiple
// favorites (matched_favorites.length > 1), show all of them — so the user
// sees that one target dish is closer to several of their seeds.
function matchedFavLine(dish, showScores) {
  const mfs = Array.isArray(dish.matched_favorites) ? dish.matched_favorites : [];
  if (mfs.length > 1) {
    const parts = mfs.map(mf =>
      `<strong>${mf.name}</strong>${showScores && mf.score != null ? ` (${Math.round(mf.score)}%)` : ""}`
    );
    return `Because you liked ${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  }
  if (mfs.length === 1) {
    const mf = mfs[0];
    return `Because you liked <strong>${mf.name}</strong>${showScores && mf.score != null ? ` (${Math.round(mf.score)}% similar)` : ""}`;
  }
  if (dish.matched_favorite) {
    return `Because you liked <strong>${dish.matched_favorite}</strong>${showScores && dish.matched_favorite_score != null ? ` (${dish.matched_favorite_score}% similar)` : ""}`;
  }
  return "";
}

let _smUid = 0;
function nextShowMoreId() { return `sm-${++_smUid}`; }

// Toggle a hidden-dishes block (called inline from the button).
function toggleShowMore(id, totalHidden) {
  const box = document.getElementById(id);
  const btn = document.getElementById(id + "-btn");
  if (!box || !btn) return;
  const collapsed = box.getAttribute("data-state") !== "expanded";
  if (collapsed) {
    box.setAttribute("data-state", "expanded");
    box.style.display = "";
    btn.textContent = "Show less";
  } else {
    box.setAttribute("data-state", "collapsed");
    box.style.display = "none";
    btn.textContent = `Show ${totalHidden} more`;
  }
}

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ══════════════════════════════════════════════════════════════════════════════
//  ENGINE TOGGLE
// ══════════════════════════════════════════════════════════════════════════════
function setEngine(engine) {
  state.engine = engine;
  document.querySelectorAll(".engine-btn").forEach((btn) => btn.classList.remove("active"));
  if (engine === "llm") {
    document.getElementById("engine-llm").classList.add("active");
  } else if (engine === "gemini") {
    document.getElementById("engine-gemini").classList.add("active");
  } else if (engine === "hybrid") {
    document.getElementById("engine-hybrid").classList.add("active");
  } else {
    document.getElementById("engine-algo").classList.add("active");
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP NAVIGATION
// ══════════════════════════════════════════════════════════════════════════════
function goToStep(n) {
  state.step = n;
  $$(".step").forEach((el) => el.classList.remove("active"));
  const el = $(`#step-${n}`);
  if (el) el.classList.add("active");
  $$(".progress-step").forEach((s, i) => {
    s.classList.remove("active", "done");
    if (i + 1 === n) s.classList.add("active");
    else if (i + 1 < n) s.classList.add("done");
  });
  $$(".progress-line").forEach((l, i) => l.classList.toggle("done", i + 1 < n));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 1 — Source Cuisine
// ══════════════════════════════════════════════════════════════════════════════
async function loadCuisines() {
  const res = await fetch("/api/cuisines");
  if (res.status === 401) return (window.location.href = "/login");
  state.cuisines = await res.json();
  renderCuisineGrid("source-cuisine-grid", state.cuisines, selectSourceCuisine);
}

function renderCuisineGrid(id, list, onClick, disabled = []) {
  document.getElementById(id).innerHTML = list
    .map((c) => {
      const dis = disabled.includes(c) ? "disabled" : "";
      return `<div class="cuisine-card ${dis}" data-cuisine="${c}" onclick="${onClick.name}('${c}')">
        <span class="flag">${FLAGS[c] || "🍽"}</span>${c}</div>`;
    })
    .join("");
}

function selectSourceCuisine(name) {
  state.sourceCuisine = name;
  $$("#source-cuisine-grid .cuisine-card").forEach((el) =>
    el.classList.toggle("selected", el.dataset.cuisine === name)
  );
  $("#btn-step1-next").disabled = false;
}

function nextStep1() {
  if (!state.sourceCuisine) return;
  // Just advance to the Diet step. Dishes load after Tier-1 constraints are set.
  goToStep(2);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 2 — Diet & Proteins (Tier 1 hard constraints)
// ══════════════════════════════════════════════════════════════════════════════
async function nextStep2() {
  // Load dishes now so the favorites grid is filtered by Tier 1.
  await loadDishes();
  goToStep(3);
}

// ── Tier-1 filter: keep only dishes the user can actually eat ──
function passesTier1(dish) {
  const diet = (state.tastePrefs.dietary || "any").toLowerCase();
  const dishDiet = (dish.dietary || "").toLowerCase();
  const isVeg = dishDiet.includes("veg") && !dishDiet.includes("non");

  // Dietary filter
  if (diet === "veg" || diet === "vegan") {
    if (!isVeg) return false;
  } else if (diet === "pescatarian") {
    if (!isVeg) {
      const prot = (dish.protein || "").toLowerCase();
      const isFish = /fish|seafood|shrimp|prawn|salmon|tuna|cod|squid|octopus|anchov|sardine/.test(prot);
      if (!isFish) return false;
    }
  }
  // "any" and "non-veg" impose no dietary filter

  // Protein whitelist (only when non-veg meat dish + whitelist set)
  if (!isVeg && Array.isArray(state.tastePrefs.allowed_proteins)) {
    const allowed = state.tastePrefs.allowed_proteins;
    if (allowed.length === 0) return true; // nothing specified, allow
    const prot = (dish.protein || "").toLowerCase();
    if (!prot) return true; // unknown protein on a meat dish — keep, don't over-filter
    const groups = {
      chicken: /chicken|poultry/,
      fish: /fish|seafood|shrimp|prawn|salmon|tuna|cod|squid|octopus|crab|lobster|mussel|clam|anchov|sardine/,
      lamb: /lamb|mutton|goat/,
      beef: /beef|veal|ox/,
      pork: /pork|ham|bacon|sausage/,
      duck: /duck|quail|rabbit|game/,
      egg: /^egg/,
    };
    const matchesAllowed = allowed.some((a) => (groups[a] || new RegExp(a)).test(prot));
    if (!matchesAllowed) return false;
  }
  return true;
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 3 — Favorite Dishes (grouped by course, Tier-1 filtered)
// ══════════════════════════════════════════════════════════════════════════════
async function loadDishes() {
  state.favoriteDishes = [];
  const res = await fetch(`/api/dishes?cuisine=${encodeURIComponent(state.sourceCuisine)}`);
  const raw = await res.json();
  // Apply Tier-1 filter once, per-group
  state.dishGroups = raw
    .map((g) => ({ course: g.course, dishes: (g.dishes || []).filter(passesTier1) }))
    .filter((g) => g.dishes.length > 0);
  // Flatten for search
  state.allDishes = [];
  state.dishGroups.forEach((g) => g.dishes.forEach((d) => state.allDishes.push(d)));
  renderCourseCounts();
  renderDishesGrouped(state.dishGroups);
  updateDishInfo();
}

// Compact dietary badge shown on every dish chip so users can tell at a glance
// what kind of dish they're picking. Covers veg / vegan / non-veg / fish / egg.
function renderDietBadge(dish) {
  const diet = (dish.dietary || "").toLowerCase();
  const prot = (dish.protein || "").toLowerCase();
  const isVeg = diet.includes("veg") && !diet.includes("non");
  const isVegan = diet === "vegan";
  const isFish = /fish|seafood|shrimp|prawn|salmon|tuna|cod|squid|octopus|crab|lobster|mussel|clam|anchov|sardine/.test(prot);
  const isEgg = /^egg/.test(prot);
  let cls, txt, title;
  if (isVegan) { cls = "diet-vegan";   txt = "🌿 Vegan";   title = "Vegan"; }
  else if (isVeg) { cls = "diet-veg";   txt = "🌱 Veg";     title = "Vegetarian"; }
  else if (isFish) { cls = "diet-fish"; txt = "🐟 Fish";    title = "Fish / Seafood"; }
  else if (isEgg) { cls = "diet-egg";   txt = "🥚 Egg";     title = "Egg"; }
  else { cls = "diet-nonveg"; txt = "🥩 Non-Veg"; title = `Non-Veg${prot ? " · " + dish.protein : ""}`; }
  return `<span class="diet-badge ${cls}" title="${title}">${txt}</span>`;
}

function renderDishesGrouped(groups) {
  const grid = document.getElementById("dish-grid");
  let html = "";
  groups.forEach((group) => {
    if (!group.dishes || group.dishes.length === 0) return;
    const icon = COURSE_ICONS[group.course] || "🍽";
    html += `<div class="course-section">
      <h3 class="course-header">${icon} ${group.course}</h3>
      <div class="dish-chips-wrap">`;
    group.dishes.forEach((d) => {
      const sel = state.favoriteDishes.includes(d.name) ? "selected" : "";
      const dietBadge = renderDietBadge(d);
      html += `<div class="dish-chip ${sel}" data-dish="${d.name}" onclick="toggleDish('${d.name.replace(/'/g, "\\'")}')">
        ${dietBadge}${d.name} <span class="cat">${d.category}</span>
      </div>`;
    });
    html += `</div></div>`;
  });
  grid.innerHTML = html;
}

function toggleDish(name) {
  const i = state.favoriteDishes.indexOf(name);
  if (i >= 0) state.favoriteDishes.splice(i, 1);
  else state.favoriteDishes.push(name);
  $$("#dish-grid .dish-chip").forEach((el) =>
    el.classList.toggle("selected", state.favoriteDishes.includes(el.dataset.dish))
  );
  updateDishInfo();
}

const MIN_FAVORITES = 3;

function renderCourseCounts() {
  const el = document.getElementById("dish-course-counts");
  if (!el) return;
  if (!state.dishGroups || state.dishGroups.length === 0) {
    el.innerHTML = "";
    return;
  }
  const parts = state.dishGroups.map((g) => {
    const icon = COURSE_ICONS[g.course] || "🍽";
    return `<span class="course-count-chip">${icon} ${g.dishes.length} ${g.course}</span>`;
  });
  el.innerHTML = `<span class="course-counts-label">Available for you:</span> ${parts.join(" ")}`;
}

function updateDishInfo() {
  const c = state.favoriteDishes.length;
  const totalAvailable = state.allDishes.length;
  const info = $("#dish-selection-info");
  if (totalAvailable === 0) {
    info.textContent =
      "No dishes match your diet & protein settings for this cuisine. Go back and broaden your preferences.";
  } else if (c === 0) {
    info.textContent = `Click on dishes you love (select at least ${MIN_FAVORITES}) — ${totalAvailable} available`;
  } else if (c < MIN_FAVORITES) {
    const need = MIN_FAVORITES - c;
    info.textContent = `${c} selected — pick ${need} more to continue`;
  } else {
    info.textContent = `${c} dish${c > 1 ? "es" : ""} selected ✓`;
  }
  $("#btn-step3-next").disabled = c < MIN_FAVORITES;
}

function filterDishes() {
  const q = $("#dish-search").value.toLowerCase();
  if (!q) {
    renderDishesGrouped(state.dishGroups);
    return;
  }
  // Filter within each group
  const filtered = state.dishGroups
    .map((g) => ({
      course: g.course,
      dishes: g.dishes.filter((d) => d.name.toLowerCase().includes(q) || d.category.toLowerCase().includes(q)),
    }))
    .filter((g) => g.dishes.length > 0);
  renderDishesGrouped(filtered);
}

function nextStep3() {
  if (state.favoriteDishes.length < MIN_FAVORITES) return;
  goToStep(4);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 4 — Taste Preferences (soft biases)
// ══════════════════════════════════════════════════════════════════════════════
function selectPref(prefKey, value, btn) {
  state.tastePrefs[prefKey] = value;
  const parent = btn.closest(".pref-options");
  parent.querySelectorAll(".pref-btn").forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");
}

function updateTogglePref() {
  state.tastePrefs.likes_creamy = $("#pref-creamy").checked;
  state.tastePrefs.likes_aromatic = $("#pref-aromatic").checked;
  state.tastePrefs.likes_sweet = $("#pref-sweet").checked;
  state.tastePrefs.likes_sour = $("#pref-sour").checked;
}

// Unified dietary selector — sets dietary + reveals/hides the meat sub-panel.
function selectDiet(value, btn) {
  state.tastePrefs.dietary = value;
  state.tastePrefs.prefer_vegetarian = false;
  const parent = btn.closest(".pref-options");
  parent.querySelectorAll(".pref-btn").forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");

  const panel = document.getElementById("protein-subpanel");
  if (value === "non-veg") {
    // Show meat sub-panel; default = all checked = no meat filter.
    panel.style.display = "";
    document.querySelectorAll(".protein-check").forEach((cb) => (cb.checked = true));
    state.tastePrefs.allowed_proteins = "any";
  } else {
    // Veg / Vegan / Pescatarian / Any — protein filter doesn't apply.
    panel.style.display = "none";
    state.tastePrefs.allowed_proteins = "any";
  }
}

// Only called from within the meat sub-panel.
function updateProteinPref() {
  const checked = Array.from(document.querySelectorAll(".protein-check:checked")).map((cb) => cb.dataset.protein);
  const all = document.querySelectorAll(".protein-check").length;
  // If all (or none) checked, treat as "any" — no hard filter.
  state.tastePrefs.allowed_proteins =
    checked.length === 0 || checked.length === all ? "any" : checked;
}

function nextStep4() {
  renderTargetCuisines();
  goToStep(5);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 5 — Target Cuisines
// ══════════════════════════════════════════════════════════════════════════════
function renderTargetCuisines() {
  renderCuisineGrid("target-cuisine-grid", state.cuisines, toggleTargetCuisine, [state.sourceCuisine]);
  state.targetCuisines = [];
  updateTargetInfo();
}

function toggleTargetCuisine(name) {
  if (name === state.sourceCuisine) return;
  const i = state.targetCuisines.indexOf(name);
  if (i >= 0) state.targetCuisines.splice(i, 1);
  else if (state.targetCuisines.length < 5) state.targetCuisines.push(name);
  $$("#target-cuisine-grid .cuisine-card").forEach((el) => {
    if (el.dataset.cuisine !== state.sourceCuisine)
      el.classList.toggle("selected", state.targetCuisines.includes(el.dataset.cuisine));
  });
  updateTargetInfo();
}

function updateTargetInfo() {
  const c = state.targetCuisines.length;
  $("#target-selection-info").textContent =
    c === 0 ? "Select 1 to 5 cuisines to explore" : `${c} selected: ${state.targetCuisines.join(", ")}`;
  $("#btn-recommend").disabled = c === 0;
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 6 — Recommendations (grouped by course)
// ══════════════════════════════════════════════════════════════════════════════
async function getRecommendations() {
  goToStep(6);

  const payload = JSON.stringify({
    source_cuisine: state.sourceCuisine,
    favorite_dishes: state.favoriteDishes,
    target_cuisines: state.targetCuisines,
    taste_preferences: state.tastePrefs,
  });
  const headers = { "Content-Type": "application/json" };

  const engines = [
    { key: "hybrid-v3", label: "🧬 Hybrid 3.0", endpoint: "/api/recommend-hybrid-v3" },
    { key: "hybrid-v2", label: "🌟 Hybrid 2.0", endpoint: "/api/recommend-hybrid-v2" },
    { key: "hybrid", label: "🔬 Hybrid 1.0", endpoint: "/api/recommend-hybrid" },
    { key: "algorithm", label: "⚙️ Algorithm", endpoint: "/api/recommend" },
  ];

  // Initialize results array and build initial UI with loading placeholders
  const engineResults = engines.map(e => ({ ...e, data: null, error: null, loading: true }));
  state.results = engineResults;
  renderComparisonResults(engineResults);

  // Fire all engines in parallel, render each as it arrives
  engines.forEach((eng, i) => {
    fetch(eng.endpoint, { method: "POST", headers, body: payload })
      .then(r => r.json())
      .then(d => {
        if (d.error) {
          engineResults[i] = { ...eng, data: null, error: String(d.error), loading: false };
        } else {
          engineResults[i] = { ...eng, data: d, error: null, loading: false };
        }
        renderComparisonResults(engineResults);
      })
      .catch(err => {
        engineResults[i] = { ...eng, data: null, error: String(err), loading: false };
        renderComparisonResults(engineResults);
      });
  });
}

function renderResults(data) {
  let html = "";

  // ── User profile card ──
  html += `<div class="profile-card">
    <h3>Your Flavor DNA <span class="profile-sub">based on ${data.favorites_used.length} ${data.source_cuisine} dishes</span></h3>
    <div class="prefs-summary">
      <span class="pref-pill">Diet: ${data.taste_preferences.dietary || "Any"}</span>
      <span class="pref-pill">Spice: ${data.taste_preferences.spice_level || "Medium"}</span>
      ${data.taste_preferences.likes_creamy ? '<span class="pref-pill">Loves Creamy</span>' : ""}
      ${data.taste_preferences.likes_aromatic ? '<span class="pref-pill">Loves Aromatic</span>' : ""}
      ${data.taste_preferences.likes_sweet ? '<span class="pref-pill">Loves Sweet</span>' : ""}
      ${data.taste_preferences.likes_sour ? '<span class="pref-pill">Loves Sour</span>' : ""}
    </div>`;

  // Show selected favorites grouped by course
  if (data.favorites_with_courses) {
    const favByCourse = {};
    data.favorites_with_courses.forEach((f) => {
      if (!favByCourse[f.course]) favByCourse[f.course] = [];
      favByCourse[f.course].push(f.name);
    });
    html += `<div class="fav-summary"><strong>Your favorites:</strong> `;
    for (const [course, names] of sortedCourseEntries(favByCourse)) {
      html += `<span class="fav-course-group">${COURSE_ICONS[course] || ""} ${course}: ${names.join(", ")}</span> `;
    }
    html += `</div>`;
  }

  html += `<div class="flavor-bars">`;
  for (const [label, val] of Object.entries(data.user_profile)) {
    html += `<div class="flavor-row">
      <span class="flavor-label">${label}</span>
      <div class="flavor-bar-bg"><div class="flavor-bar-fill" style="width:${(val / 10) * 100}%"></div></div>
      <span class="flavor-val">${val}</span>
    </div>`;
  }
  html += `</div></div>`;

  // ── Engine badge ──
  const engineLabel = data.engine === "hybrid-v3" ? "🧬 Hybrid 3.0" : data.engine === "hybrid-v2" ? "🌟 Hybrid 2.0" : data.engine === "hybrid" ? "🔬 Hybrid 1.0" : "⚙️ Algorithm";
  const engineClass = data.engine === "hybrid-v3" ? "hybrid-v3" : data.engine === "hybrid-v2" ? "hybrid-v2" : data.engine === "hybrid" ? "hybrid" : "algo";
  html += `<div class="engine-badge-row">
    <span class="engine-badge ${engineClass}">${engineLabel} recommendations</span>
  </div>`;

  // ── Per-cuisine results, grouped by course ──
  for (const [cuisine, info] of Object.entries(data.recommendations)) {
    // Handle API errors for this cuisine
    if (info.error && (!info.courses || Object.keys(info.courses).length === 0)) {
      html += `<div class="results-section">
        <div class="cuisine-result-header">
          <span style="font-size:1.6rem">${FLAGS[cuisine] || "🍽"}</span>
          <h3>${cuisine}</h3>
        </div>
        <p style="color:#dc2626;padding:1rem;font-weight:500">⚠️ ${info.error}</p>
      </div>`;
      continue;
    }

    const simPct = info.cuisine_similarity != null ? (info.cuisine_similarity * 100).toFixed(0) : "?";
    const simColor = info.cuisine_similarity > 0.3 ? "var(--accent)" : info.cuisine_similarity > 0 ? "#b45309" : "#dc2626";

    html += `<div class="results-section">
      <div class="cuisine-result-header">
        <span style="font-size:1.6rem">${FLAGS[cuisine] || "🍽"}</span>
        <h3>${cuisine}</h3>
        <span class="sim-badge" style="background:${simColor}15;color:${simColor}">
          ${simPct !== "?" ? ((info.cuisine_similarity > 0 ? "+" : "") + simPct + "% similarity to " + data.source_cuisine) : ""}
        </span>
        <span class="eval-badge">${info.total_dishes_evaluated || 0} dishes evaluated</span>
      </div>`;

    const courses = info.courses || {};
    if (Object.keys(courses).length === 0) {
      html += `<p style="color:var(--text-muted);padding:1rem">No dishes match your dietary preference in this cuisine.</p>`;
    }

    for (const [courseName, dishes] of sortedCourseEntries(courses)) {
      const courseIcon = COURSE_ICONS[courseName] || "🍽";
      const { visible, hidden } = splitVisibleHidden(dishes, info.visible_per_course);
      html += `<div class="course-result-section">
        <h4 class="course-result-header">${courseIcon} ${courseName} <span class="course-count">(${visible.length}${hidden.length ? "+" + hidden.length : ""} picks)</span></h4>`;

      visible.forEach((dish, i) => {
        html += renderDishCard(dish, i, data.user_profile);
      });

      if (hidden.length) {
        const id = nextShowMoreId();
        html += `<div id="${id}" class="hidden-dishes" data-state="collapsed" style="display:none">`;
        hidden.forEach((dish, i) => {
          html += renderDishCard(dish, visible.length + i, data.user_profile);
        });
        html += `</div>`;
        html += `<button id="${id}-btn" class="show-more-btn" onclick="toggleShowMore('${id}', ${hidden.length})">Show ${hidden.length} more</button>`;
      }

      html += `</div>`;
    }

    html += `</div>`;
  }

  $("#results-container").innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════════
//  SIDE-BY-SIDE COMPARISON VIEW
// ══════════════════════════════════════════════════════════════════════════════
function renderComparisonResults(engineResults) {
  let html = "";

  // Use the first successful result for profile/favorites display
  const first = engineResults.find(e => e.data);
  if (first && first.data.user_profile && Object.keys(first.data.user_profile).length) {
    const d = first.data;
    html += `<div class="profile-card">
      <h3>Your Flavor DNA <span class="profile-sub">based on ${d.favorites_used.length} ${d.source_cuisine} dish${d.favorites_used.length > 1 ? "es" : ""}</span></h3>
      <div class="prefs-summary">
        <span class="pref-pill">Diet: ${d.taste_preferences.dietary || "Any"}</span>
        <span class="pref-pill">Spice: ${d.taste_preferences.spice_level || "Medium"}</span>
      </div>`;
    if (d.favorites_with_courses) {
      html += `<div class="fav-summary"><strong>Your favorites:</strong> `;
      d.favorites_with_courses.forEach(f => {
        html += `<span class="fav-course-group">${COURSE_ICONS[f.course] || ""} ${f.name}</span> `;
      });
      html += `</div>`;
    }
    html += `</div>`;
  }

  // Collect all cuisines — use target cuisines from state as baseline
  const allCuisines = new Set(state.targetCuisines);
  engineResults.forEach(e => {
    if (e.data && e.data.recommendations) {
      Object.keys(e.data.recommendations).forEach(c => allCuisines.add(c));
    }
  });

  // For each target cuisine, show engines side by side
  for (const cuisine of allCuisines) {
    html += `<div class="comparison-cuisine-section">
      <div class="cuisine-result-header">
        <span style="font-size:1.6rem">${FLAGS[cuisine] || "🍽"}</span>
        <h3>${cuisine}</h3>
      </div>
      <div class="comparison-grid">`;

    for (const eng of engineResults) {
      const engineClass = eng.key;
      const badgeColors = {
        algorithm: "background:#dbeafe;color:#1d4ed8",
        llm: "background:#ede9fe;color:#6d28d9",
        gemini: "background:#dbeafe;color:#1d4ed8",
        hybrid: "background:#dcfce7;color:#15803d",
      };

      html += `<div class="comparison-column comparison-col-${engineClass}">
        <div class="comparison-engine-header">
          <span class="engine-badge" style="${badgeColors[engineClass] || ""}">${eng.label}</span>
        </div>`;

      if (eng.loading) {
        html += `<div class="comparison-loading"><div class="spinner-sm"></div><span>Loading...</span></div>`;
      } else if (!eng.data || eng.error) {
        html += `<div class="comparison-error">⚠️ ${eng.error || "No results"}</div>`;
      } else {
        const info = eng.data.recommendations[cuisine];
        if (!info) {
          html += `<div class="comparison-error">No results for ${cuisine}</div>`;
        } else {
          const courses = info.courses || {};
          if (Object.keys(courses).length === 0) {
            html += `<div class="comparison-error">No matching dishes</div>`;
          } else {
            for (const [courseName, dishes] of sortedCourseEntries(courses)) {
              const courseIcon = COURSE_ICONS[courseName] || "🍽";
              const { visible, hidden } = splitVisibleHidden(dishes, info.visible_per_course);
              html += `<div class="comparison-course">
                <h5 class="comparison-course-title">${courseIcon} ${courseName}</h5>`;
              visible.forEach((dish, i) => {
                html += renderCompactCard(dish, i, eng.key);
              });
              if (hidden.length) {
                const id = nextShowMoreId();
                html += `<div id="${id}" class="hidden-dishes" data-state="collapsed" style="display:none">`;
                hidden.forEach((dish, i) => {
                  html += renderCompactCard(dish, visible.length + i, eng.key);
                });
                html += `</div>`;
                html += `<button id="${id}-btn" class="show-more-btn show-more-btn-compact" onclick="toggleShowMore('${id}', ${hidden.length})">Show ${hidden.length} more</button>`;
              }
              html += `</div>`;
            }
          }
        }
      }
      html += `</div>`; // comparison-column
    }

    html += `</div></div>`; // comparison-grid, comparison-cuisine-section
  }

  $("#results-container").innerHTML = html;
}

function renderCompactCard(dish, i, engineKey) {
  const borderColors = { algorithm: "#3b82f6", hybrid: "#16a34a", "hybrid-v2": "#f59e0b", "hybrid-v3": "#9333ea" };
  const engineLabels = { algorithm: "Algorithm", hybrid: "Hybrid 1.0", "hybrid-v2": "Hybrid 2.0", "hybrid-v3": "Hybrid 3.0" };
  const border = borderColors[engineKey] || "#ccc";
  const dishData = JSON.stringify({...dish, _engine: engineKey, _engineLabel: engineLabels[engineKey] || engineKey}).replace(/'/g, "&#39;");
  return `<div class="compact-card" style="border-left:3px solid ${border}" onclick='showCompactDetail(${dishData})'>
    <div class="compact-card-top">
      <span class="compact-rank">${i + 1}</span>
      <div class="compact-info">
        <strong>${dish.dish_name}</strong>
        ${(() => { const l = matchedFavLine(dish, false); return l ? `<div class="compact-match">${l}</div>` : ""; })()}
        <div class="compact-meta">
          <span>${dish.category || ""}</span>
          <span>${dish.dietary || ""}</span>
          ${dish.protein ? `<span>${dish.protein}</span>` : ""}
        </div>
        ${dish.why && engineKey === "hybrid" ? `<p class="compact-why">${dish.why}</p>` : `<p class="compact-desc">${dish.description || ""}</p>`}
      </div>
      <div class="compact-score">
        <span class="compact-score-pct">${dish.score}%</span>
        <span class="compact-score-label">match</span>
      </div>
    </div>
  </div>`;
}

function showCompactDetail(dish) {
  const borderColors = { algorithm: "#3b82f6", hybrid: "#16a34a", "hybrid-v2": "#f59e0b", "hybrid-v3": "#9333ea" };
  const border = borderColors[dish._engine] || "#ccc";
  let html = `<div style="border-left:4px solid ${border};padding-left:1rem">`;
  html += `<h2 style="margin:0 0 0.25rem">${dish.dish_name}</h2>`;
  html += `<span class="engine-badge" style="font-size:0.7rem;padding:2px 8px;border-radius:8px;background:${border}15;color:${border}">${dish._engineLabel}</span>`;
  html += `<p style="color:var(--text-muted);margin:0.5rem 0">${dish.category || ""} | ${dish.dietary || ""} ${dish.protein ? "| " + dish.protein : ""}</p>`;

  if (dish.matched_favorite) {
    html += `<div class="matched-fav-badge" style="margin:0.5rem 0">Because you liked <strong>${dish.matched_favorite}</strong> (${dish.matched_favorite_score || dish.score}% match)</div>`;
  }

  html += `<p style="font-size:0.85rem;margin:0.5rem 0">${dish.description || ""}</p>`;
  if (dish.ingredients) {
    html += `<p style="font-size:0.82rem"><strong>Ingredients:</strong> ${dish.ingredients}</p>`;
  }
  if (dish.why) {
    html += `<div class="result-why" style="margin:0.5rem 0">${dish.why}</div>`;
  }

  // Score
  html += `<div style="margin:0.75rem 0;padding:0.5rem;background:#f8fafc;border-radius:8px">
    <strong style="font-size:1.1rem;color:${border}">${dish.score}% match</strong>`;
  if (dish.flavor_distance != null) {
    html += `<span style="margin-left:1rem;font-size:0.8rem;color:var(--text-muted)">Flavor distance: ${dish.flavor_distance}</span>`;
  }
  html += `</div>`;

  // Flavor profile comparison (hybrid)
  if (dish.flavor && dish.seed_flavor) {
    html += `<div style="margin-top:0.75rem"><h4 style="margin-bottom:0.4rem">Flavor Comparison</h4>`;
    html += `<div style="display:grid;grid-template-columns:80px 1fr 1fr;gap:2px;font-size:0.75rem">`;
    html += `<div style="font-weight:600">Dimension</div><div style="font-weight:600">Your Favorite</div><div style="font-weight:600">This Dish</div>`;
    for (const [dim, val] of Object.entries(dish.flavor)) {
      const seedVal = dish.seed_flavor[dim] || 0;
      html += `<div>${dim}</div><div>${seedVal}</div><div>${val}</div>`;
    }
    html += `</div></div>`;
  }

  // Scoring breakdown (algorithm)
  if (dish.scoring && dish.scoring.cosine_sim) {
    html += `<div style="margin-top:0.75rem"><h4 style="margin-bottom:0.4rem">Score Breakdown</h4>
      <div style="font-size:0.8rem">
        Flavor: ${dish.scoring.cosine_sim}% | Method: ${dish.scoring.cooking_method}% | Ingredients: ${dish.scoring.ingredient_match}% | Temp: ${dish.scoring.temperature_match}% | Diet: ${dish.scoring.dietary_compat}%
      </div></div>`;
  }

  // Flavor bridge (LLM/Gemini)
  if (dish.flavor_bridge) {
    html += `<div class="flavor-bridge" style="margin-top:0.5rem">${dish.flavor_bridge}</div>`;
  }

  html += `</div>`;

  $("#modal-body").innerHTML = html;
  $("#detail-modal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function renderDishCard(dish, i, userProfile) {
  const isLLM = state.engine === "llm";
  const isGemini = state.engine === "gemini";
  const isHybrid = state.engine === "hybrid";
  const isAI = isLLM || isGemini;
  const cardClass = isHybrid ? ' hybrid-card' : isGemini ? ' gemini-card' : isLLM ? ' llm-card' : '';
  let html = `<div class="result-card${cardClass}" onclick='showDetail(${JSON.stringify(dish).replace(/'/g, "&#39;")}, ${JSON.stringify(userProfile).replace(/'/g, "&#39;")})'>
    <div class="result-card-top">
      <div class="rank-badge rank-${i + 1}">${i + 1}</div>
      <div class="result-info">
        <h4>${dish.dish_name}</h4>`;

  // "Because you liked X" badge (supports multi-favorite attribution)
  {
    const line = matchedFavLine(dish, !isAI);
    if (line) html += `<div class="matched-fav-badge">${line}</div>`;
  }

  html += `<div class="result-meta">
          <span class="result-tag">${dish.category}</span>
          <span class="result-tag">${dish.dietary}</span>
          ${dish.protein ? `<span class="result-tag">${dish.protein}</span>` : ''}
          ${dish.spice_level ? `<span class="result-tag">Spice: ${dish.spice_level}</span>` : ''}
        </div>
        <p class="result-desc">${dish.description}</p>
        ${dish.ingredients ? `<p class="result-ingredients"><strong>Ingredients:</strong> ${dish.ingredients}</p>` : ''}
        <div class="result-why">${dish.why}</div>`;

  if (isAI) {
    // AI mode (Groq or Gemini): show match score + flavor bridge
    const dotClass = isGemini ? 'gemini' : 'llm';
    const aiLabel = isGemini ? 'Gemini Match' : 'AI Match';
    html += `<div class="mini-scores llm-scores">
          <span class="mini-score"><span class="mini-dot ${dotClass}"></span>${aiLabel}: ${dish.score}%</span>
          ${dish.flavor_bridge ? `<span class="flavor-bridge">${dish.flavor_bridge}</span>` : ''}
        </div>`;
  } else {
    // Algorithm mode: show detailed scoring breakdown
    html += `<div class="mini-scores">
          <span class="mini-score"><span class="mini-dot cos"></span>Flavor: ${dish.scoring.cosine_sim}%</span>
          <span class="mini-score"><span class="mini-dot cook"></span>Method: ${dish.scoring.cooking_method}%</span>
          <span class="mini-score"><span class="mini-dot ing"></span>Ingredients: ${dish.scoring.ingredient_match}%</span>
          <span class="mini-score"><span class="mini-dot temp"></span>Temp: ${dish.scoring.temperature_match}%</span>
          <span class="mini-score"><span class="mini-dot ingcat"></span>IngType: ${dish.scoring.ingredient_category}%</span>
          <span class="mini-score"><span class="mini-dot diet"></span>Diet: ${dish.scoring.dietary_compat}%</span>
        </div>`;
  }

  if (dish.similar_alternatives && dish.similar_alternatives.length > 0) {
    html += `<div class="alt-row">Similar: `;
    dish.similar_alternatives.forEach((alt, ai) => {
      html += `${ai > 0 ? " | " : ""}<strong>${alt.name}</strong> (${alt.similarity_to_this}% similar, scored ${alt.score}%)`;
    });
    html += `</div>`;
  }

  html += `</div>
      <div class="score-area">
        <span class="score-pct">${dish.score}%</span>
        <span class="score-label">match</span>
      </div>
    </div>
  </div>`;
  return html;
}

// ══════════════════════════════════════════════════════════════════════════════
//  DETAIL MODAL
// ══════════════════════════════════════════════════════════════════════════════
function showDetail(dish, userProfile) {
  let html = "";

  html += `<h2 class="modal-title">${dish.dish_name}</h2>
    <p class="modal-subtitle">${dish.course} &rsaquo; ${dish.category} | ${dish.dietary} | ${dish.protein} | Spice: ${dish.spice_level}</p>`;

  if (dish.matched_favorite) {
    html += `<div class="matched-fav-badge" style="margin-bottom:0.75rem">Recommended because you liked <strong>${dish.matched_favorite}</strong> (${dish.matched_favorite_score}% match)</div>`;
  }

  html += `<p style="font-size:0.9rem;color:var(--text-muted);margin-bottom:0.5rem">${dish.description}</p>
    <p style="font-size:0.85rem;margin-bottom:1.25rem"><strong>Ingredients:</strong> ${dish.ingredients}</p>`;

  // Score breakdown
  html += `<div class="detail-section">
    <h4>Score Breakdown</h4>
    <div class="score-breakdown-grid">
      <div class="score-item">
        <div class="score-item-label">Overall Match</div>
        <div class="score-item-val" style="color:var(--primary)">${dish.score}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Flavor Match (weighted cosine)</div>
        <div class="score-item-val">${dish.scoring.cosine_sim}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Cooking Method Match</div>
        <div class="score-item-val">${dish.scoring.cooking_method}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Ingredient Match</div>
        <div class="score-item-val">${dish.scoring.ingredient_match}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Cuisine Affinity (${state.sourceCuisine} link)</div>
        <div class="score-item-val">${dish.scoring.cuisine_affinity}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Temperature Match</div>
        <div class="score-item-val">${dish.scoring.temperature_match}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Ingredient Type Match</div>
        <div class="score-item-val">${dish.scoring.ingredient_category}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Dietary Compatibility</div>
        <div class="score-item-val">${dish.scoring.dietary_compat}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Dish Importance (popularity)</div>
        <div class="score-item-val">${dish.scoring.dish_importance}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Flavor Deviation Penalty</div>
        <div class="score-item-val" style="color:${dish.scoring.deviation_penalty > 0 ? '#ef4444' : 'inherit'}">-${dish.scoring.deviation_penalty}%</div>
      </div>
    </div>
  </div>`;

  // Flavor comparison
  html += `<div class="detail-section">
    <h4>Flavor Profile: You vs This Dish</h4>
    <div style="display:flex;gap:1rem;margin-bottom:0.5rem;font-size:0.75rem">
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:var(--primary);vertical-align:middle"></span> Your profile</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:#3b82f6;vertical-align:middle"></span> This dish</span>
    </div>
    <div class="flavor-compare-grid">`;

  for (const label of Object.keys(userProfile)) {
    const you = userProfile[label] || 0;
    const them = dish.flavor[label] || 0;
    const diff = Math.abs(you - them);
    const diffColor = diff <= 1 ? "var(--accent)" : diff <= 3 ? "#b45309" : "#dc2626";

    html += `<div class="flavor-compare-row">
      <span class="flavor-compare-label">${label}</span>
      <div class="fcbar-wrap"><div class="fcbar fcbar-you" style="width:${(you / 10) * 100}%"></div></div>
      <div class="fcbar-wrap"><div class="fcbar fcbar-dish" style="width:${(them / 10) * 100}%"></div></div>
      <span style="font-size:0.8rem;font-weight:700;text-align:right">${you}</span>
      <span style="font-size:0.8rem;font-weight:700;text-align:right;color:${diffColor}">${them}</span>
    </div>`;
  }
  html += `</div></div>`;

  // Explanation
  html += `<div class="detail-section">
    <h4>Why This Was Recommended</h4>
    <div class="result-why" style="font-size:0.88rem;line-height:1.5">${dish.why}</div>
  </div>`;

  // Similar alternatives
  if (dish.similar_alternatives && dish.similar_alternatives.length > 0) {
    html += `<div class="detail-section">
      <h4>Similar Dishes (for comparison)</h4>`;
    dish.similar_alternatives.forEach((alt) => {
      html += `<div style="background:#f9fafb;padding:0.6rem 0.8rem;border-radius:10px;margin-bottom:0.4rem">
        <strong>${alt.name}</strong> — ${alt.similarity_to_this}% similar, scored ${alt.score}% match
        <div style="font-size:0.78rem;color:var(--text-muted);margin-top:0.15rem">${alt.score_diff_reason}</div>
      </div>`;
    });
    html += `</div>`;
  }

  $("#modal-body").innerHTML = html;
  $("#detail-modal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closeModal(e) { if (e.target === $("#detail-modal")) closeModalForce(); }
function closeModalForce() { $("#detail-modal").style.display = "none"; document.body.style.overflow = ""; }

// ══════════════════════════════════════════════════════════════════════════════
//  AUTH & NAV
// ══════════════════════════════════════════════════════════════════════════════
async function doLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
}

// ── Change Password ──
function showChangePassword() {
  $("#pw-current").value = "";
  $("#pw-new").value = "";
  $("#pw-confirm").value = "";
  $("#pw-error").style.display = "none";
  $("#pw-success").style.display = "none";
  $("#pw-modal").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closePwModal() {
  $("#pw-modal").style.display = "none";
  document.body.style.overflow = "";
}

async function handleChangePassword(e) {
  e.preventDefault();
  const current = $("#pw-current").value;
  const newPw = $("#pw-new").value;
  const confirm = $("#pw-confirm").value;

  $("#pw-error").style.display = "none";
  $("#pw-success").style.display = "none";

  if (newPw !== confirm) {
    $("#pw-error").textContent = "New passwords don't match";
    $("#pw-error").style.display = "block";
    return false;
  }

  const res = await fetch("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: current, new_password: newPw }),
  });
  const data = await res.json();

  if (data.error) {
    $("#pw-error").textContent = data.error;
    $("#pw-error").style.display = "block";
  } else {
    $("#pw-success").textContent = "Password changed successfully!";
    $("#pw-success").style.display = "block";
    setTimeout(closePwModal, 1500);
  }
  return false;
}

function startOver() {
  state.sourceCuisine = null;
  state.favoriteDishes = [];
  state.targetCuisines = [];
  state.results = null;
  state.tastePrefs = { dietary: "any", spice_level: "medium", likes_creamy: false, likes_aromatic: false, likes_sweet: false, likes_sour: false, allowed_proteins: "any", prefer_vegetarian: false };
  $("#btn-step1-next").disabled = true;
  $$("#source-cuisine-grid .cuisine-card").forEach((el) => el.classList.remove("selected"));
  $$(".pref-btn").forEach((b) => b.classList.remove("selected"));
  $$('.pref-btn[data-val="any"]').forEach((b) => b.classList.add("selected"));
  $$('.pref-btn[data-val="medium"]').forEach((b) => b.classList.add("selected"));
  $$("#pref-creamy, #pref-aromatic, #pref-sweet, #pref-sour").forEach((cb) => (cb.checked = false));
  // Reset unified dietary UI: hide protein sub-panel, re-check all meats (default)
  const panel = document.getElementById("protein-subpanel");
  if (panel) panel.style.display = "none";
  $$(".protein-check").forEach((cb) => (cb.checked = true));
  goToStep(1);
}

document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModalForce(); });

document.addEventListener("DOMContentLoaded", () => {
  loadCuisines();
  goToStep(1);
});
