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
  },
  results: null,
};

const FLAGS = {
  American:"🇺🇸",Brazilian:"🇧🇷",Chinese:"🇨🇳",Colombian:"🇨🇴",Croatian:"🇭🇷",
  French:"🇫🇷",Georgian:"🇬🇪",Greek:"🇬🇷",Hungarian:"🇭🇺",Indian:"🇮🇳",
  Indonesian:"🇮🇩",Italian:"🇮🇹",Japanese:"🇯🇵",Korean:"🇰🇷",Lebanese:"🇱🇧",
  Mexican:"🇲🇽",Peruvian:"🇵🇪",Polish:"🇵🇱",Portuguese:"🇵🇹",Serbian:"🇷🇸",
  Spanish:"🇪🇸",Thai:"🇹🇭",Turkish:"🇹🇷",Vietnamese:"🇻🇳",
};

const COURSE_ICONS = {
  "Appetizers": "🥗", "Soups": "🍲", "Salads": "🥬", "Entrees": "🍛",
  "Sides & Breads": "🍞", "Snacks & Street Food": "🥟", "Desserts": "🍮", "Drinks": "🥤",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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
  loadDishes();
  goToStep(2);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 2 — Favorite Dishes (grouped by course)
// ══════════════════════════════════════════════════════════════════════════════
async function loadDishes() {
  state.favoriteDishes = [];
  const res = await fetch(`/api/dishes?cuisine=${encodeURIComponent(state.sourceCuisine)}`);
  state.dishGroups = await res.json();
  // Flatten for search
  state.allDishes = [];
  state.dishGroups.forEach((g) => g.dishes.forEach((d) => state.allDishes.push(d)));
  renderDishesGrouped(state.dishGroups);
  updateDishInfo();
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
      const dietIcon = d.dietary.toLowerCase().includes("veg") && !d.dietary.toLowerCase().includes("non") ? "🌱" : "";
      html += `<div class="dish-chip ${sel}" data-dish="${d.name}" onclick="toggleDish('${d.name.replace(/'/g, "\\'")}')">
        ${d.name} <span class="cat">${d.category}</span>${dietIcon ? `<span class="diet-tag">${dietIcon}</span>` : ""}
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

function updateDishInfo() {
  const c = state.favoriteDishes.length;
  $("#dish-selection-info").textContent =
    c === 0 ? "Click on dishes you love (select at least 3)" : `${c} dish${c > 1 ? "es" : ""} selected`;
  $("#btn-step2-next").disabled = c < 3;
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

function nextStep2() {
  if (state.favoriteDishes.length < 3) return;
  goToStep(3);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 3 — Taste Preferences
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

function nextStep3() {
  renderTargetCuisines();
  goToStep(4);
}

// ══════════════════════════════════════════════════════════════════════════════
//  STEP 4 — Target Cuisines
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
//  STEP 5 — Recommendations (grouped by course)
// ══════════════════════════════════════════════════════════════════════════════
async function getRecommendations() {
  goToStep(5);
  $("#results-container").innerHTML = `<div class="loading"><div class="spinner"></div><p>Analyzing flavor profiles & ingredients across ${state.targetCuisines.length} cuisine(s)...</p></div>`;

  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_cuisine: state.sourceCuisine,
      favorite_dishes: state.favoriteDishes,
      target_cuisines: state.targetCuisines,
      taste_preferences: state.tastePrefs,
    }),
  });

  const data = await res.json();
  if (data.error) {
    $("#results-container").innerHTML = `<p style="color:red;padding:2rem">${data.error}</p>`;
    return;
  }
  state.results = data;
  renderResults(data);
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
    for (const [course, names] of Object.entries(favByCourse)) {
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

  // ── Per-cuisine results, grouped by course ──
  for (const [cuisine, info] of Object.entries(data.recommendations)) {
    const simPct = (info.cuisine_similarity * 100).toFixed(0);
    const simColor = info.cuisine_similarity > 0.3 ? "var(--accent)" : info.cuisine_similarity > 0 ? "#b45309" : "#dc2626";

    html += `<div class="results-section">
      <div class="cuisine-result-header">
        <span style="font-size:1.6rem">${FLAGS[cuisine] || "🍽"}</span>
        <h3>${cuisine}</h3>
        <span class="sim-badge" style="background:${simColor}15;color:${simColor}">
          ${info.cuisine_similarity > 0 ? "+" : ""}${simPct}% similarity to ${data.source_cuisine}
        </span>
        <span class="eval-badge">${info.total_dishes_evaluated} dishes evaluated</span>
      </div>`;

    const courses = info.courses || {};
    if (Object.keys(courses).length === 0) {
      html += `<p style="color:var(--text-muted);padding:1rem">No dishes match your dietary preference in this cuisine.</p>`;
    }

    for (const [courseName, dishes] of Object.entries(courses)) {
      const courseIcon = COURSE_ICONS[courseName] || "🍽";
      html += `<div class="course-result-section">
        <h4 class="course-result-header">${courseIcon} ${courseName} <span class="course-count">(${dishes.length} picks)</span></h4>`;

      dishes.forEach((dish, i) => {
        html += renderDishCard(dish, i, data.user_profile);
      });

      html += `</div>`;
    }

    html += `</div>`;
  }

  $("#results-container").innerHTML = html;
}

function renderDishCard(dish, i, userProfile) {
  let html = `<div class="result-card" onclick='showDetail(${JSON.stringify(dish).replace(/'/g, "&#39;")}, ${JSON.stringify(userProfile).replace(/'/g, "&#39;")})'>
    <div class="result-card-top">
      <div class="rank-badge rank-${i + 1}">${i + 1}</div>
      <div class="result-info">
        <h4>${dish.dish_name}</h4>`;

  // "Because you liked X" badge
  if (dish.matched_favorite) {
    html += `<div class="matched-fav-badge">Because you liked <strong>${dish.matched_favorite}</strong> (${dish.matched_favorite_score}% similar)</div>`;
  }

  html += `<div class="result-meta">
          <span class="result-tag">${dish.category}</span>
          <span class="result-tag">${dish.dietary}</span>
          <span class="result-tag">${dish.protein}</span>
          <span class="result-tag">Spice: ${dish.spice_level}</span>
        </div>
        <p class="result-desc">${dish.description}</p>
        <p class="result-ingredients"><strong>Ingredients:</strong> ${dish.ingredients}</p>
        <div class="result-why">${dish.why}</div>
        <div class="mini-scores">
          <span class="mini-score"><span class="mini-dot cos"></span>Flavor: ${dish.scoring.cosine_sim}%</span>
          <span class="mini-score"><span class="mini-dot ing"></span>Ingredients: ${dish.scoring.ingredient_match}%</span>
          <span class="mini-score"><span class="mini-dot euc"></span>Distance: ${dish.scoring.euclidean_sim}%</span>
          <span class="mini-score"><span class="mini-dot cui"></span>Cuisine: ${dish.scoring.cuisine_affinity}%</span>
          <span class="mini-score"><span class="mini-dot imp"></span>Importance: ${dish.scoring.dish_importance}%</span>
        </div>`;

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
        <div class="score-item-label">Flavor Cosine (vector match)</div>
        <div class="score-item-val">${dish.scoring.cosine_sim}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Ingredient Match (shared ingredients)</div>
        <div class="score-item-val">${dish.scoring.ingredient_match}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Euclidean Similarity (distance)</div>
        <div class="score-item-val">${dish.scoring.euclidean_sim}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Cuisine Affinity (${state.sourceCuisine} link)</div>
        <div class="score-item-val">${dish.scoring.cuisine_affinity}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Dish Importance (popularity)</div>
        <div class="score-item-val">${dish.scoring.dish_importance}%</div>
      </div>
      <div class="score-item">
        <div class="score-item-label">Spice Preference Bonus</div>
        <div class="score-item-val">${dish.scoring.spice_bonus}%</div>
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
  state.tastePrefs = { dietary: "any", spice_level: "medium", likes_creamy: false, likes_aromatic: false, likes_sweet: false, likes_sour: false };
  $("#btn-step1-next").disabled = true;
  $$("#source-cuisine-grid .cuisine-card").forEach((el) => el.classList.remove("selected"));
  $$(".pref-btn").forEach((b) => b.classList.remove("selected"));
  $$('.pref-btn[data-val="any"]').forEach((b) => b.classList.add("selected"));
  $$('.pref-btn[data-val="medium"]').forEach((b) => b.classList.add("selected"));
  $$("#pref-creamy, #pref-aromatic, #pref-sweet, #pref-sour").forEach((cb) => (cb.checked = false));
  goToStep(1);
}

document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModalForce(); });

document.addEventListener("DOMContentLoaded", () => {
  loadCuisines();
  goToStep(1);
});
