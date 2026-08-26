const page = document.body.dataset.page || "predict";
const isBacktest = page === "backtest";

const form = document.getElementById("generate-form");
const drawsInput = document.getElementById("draws");
const ticketsInput = document.getElementById("tickets");
const reviewDrawsInput = document.getElementById("review-draws");
const showPredictionsInput = document.getElementById("show-predictions");
const betTypeSelect = document.getElementById("bet-type");
const pickCountInput = document.getElementById("pick-count");
const bankerCountInput = document.getElementById("banker-count");
const trailerCountInput = document.getElementById("trailer-count");
const drawsValue = document.getElementById("draws-value");
const ticketsValue = document.getElementById("tickets-value");
const reviewValue = document.getElementById("review-value");
const showPredValue = document.getElementById("show-pred-value");
const pickValue = document.getElementById("pick-value");
const bankerValue = document.getElementById("banker-value");
const trailerValue = document.getElementById("trailer-value");
const pickHint = document.getElementById("pick-hint");
const bankerHint = document.getElementById("banker-hint");
const submitBtn = document.getElementById("submit-btn");
const spinner = submitBtn.querySelector(".spinner");
const btnLabel = submitBtn.querySelector(".btn-label");
const errorBanner = document.getElementById("error");
const resultsSection = document.getElementById("results");
const backtestSection = document.getElementById("backtest-results");
const disclaimer = document.getElementById("disclaimer");

let currentLang = localStorage.getItem("marksix-lang") || "zh";
let lastResult = null;
let lastBacktest = null;
let isLoading = false;

function t(key, vars = {}) {
  const dict = I18N[currentLang] || I18N.zh;
  let text = dict[key] ?? I18N.en[key] ?? key;
  Object.entries(vars).forEach(([name, value]) => {
    text = text.replaceAll(`{${name}}`, String(value));
  });
  return text;
}

function betLabel(betType) {
  const key = {
    single: "betSingle",
    multiple: "betMultiple",
    banker: "betBanker",
  }[betType];
  return key ? t(key) : betType;
}

function formatPrize(comparison) {
  if (!comparison?.prize_tier) {
    return t("noPrize");
  }
  const name = t(`prize${comparison.prize_tier}`);
  const fixed = comparison.prize?.fixed_prize_hkd;
  if (fixed != null) {
    return `${name} · $${Number(fixed).toLocaleString()}`;
  }
  return `${name} · ${t("prizeVariable")}`;
}

function applyLanguage() {
  document.documentElement.lang = currentLang === "zh" ? "zh-HK" : "en";
  document.title = t(isBacktest ? "pageTitleBacktest" : "pageTitle");

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });

  document.querySelectorAll("[data-i18n-option]").forEach((el) => {
    el.textContent = t(el.dataset.i18nOption);
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === currentLang);
  });

  document.querySelectorAll(".lang-zh").forEach((el) => {
    el.hidden = currentLang !== "zh";
  });
  document.querySelectorAll(".lang-en").forEach((el) => {
    el.hidden = currentLang !== "en";
  });

  updateHints();
  setLoading(isLoading);
  updateSuggestionsTitle();
  if (drawsInput && drawsValue) {
    const draws = Number(drawsInput.value);
    drawsValue.textContent = draws >= 1050 ? t("drawsAll") : drawsInput.value;
  }

  if (lastResult && !isBacktest && resultsSection) {
    renderResults(lastResult, false);
  }
  if (lastBacktest && isBacktest && backtestSection) {
    renderBacktest(lastBacktest, false);
  }
}

function updateSuggestionsTitle(betType = null) {
  const title = document.getElementById("suggestions-title");
  if (!title || !betTypeSelect) return;
  const type = betType || lastResult?.bet_type || betTypeSelect.value || "single";
  title.textContent = `${t("suggested")} ${betLabel(type)}`;
}

function combinations(n, k) {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  let result = 1;
  for (let i = 1; i <= k; i += 1) {
    result = (result * (n - k + i)) / i;
  }
  return Math.round(result);
}

function formatCost(units) {
  return t("costUnits", { units, cost: units * 10 });
}

function updateModeFields() {
  if (!betTypeSelect) return;
  const mode = betTypeSelect.value;
  document.querySelectorAll(".mode-field").forEach((field) => {
    const modes = (field.dataset.modes || "").split(/\s+/);
    field.hidden = !modes.includes(mode);
  });
  updateHints();
}

function updateHints() {
  if (!pickCountInput || !pickValue || !pickHint) return;
  const pick = Number(pickCountInput.value);
  pickValue.textContent = String(pick);
  pickHint.textContent = t("pickHint", {
    n: pick,
    cost: formatCost(combinations(pick, 6)),
  });

  if (!bankerCountInput || !trailerCountInput) return;
  const bankers = Number(bankerCountInput.value);
  const remaining = 6 - bankers;
  const minTrailers = Math.max(remaining, 1);
  if (Number(trailerCountInput.value) < minTrailers) {
    trailerCountInput.value = String(minTrailers);
  }
  trailerCountInput.min = String(minTrailers);

  const trailers = Number(trailerCountInput.value);
  bankerValue.textContent = String(bankers);
  trailerValue.textContent = String(trailers);
  bankerHint.textContent = t("bankerHint", {
    b: bankers,
    trailers,
    r: remaining,
    cost: formatCost(combinations(trailers, remaining)),
  });
}

function ballElement(
  number,
  color,
  { small = false, special = false, banker = false, hit = false, miss = false } = {}
) {
  const el = document.createElement("span");
  el.className = `ball ${color}${small ? " small" : ""}${special ? " special" : ""}${
    banker ? " banker" : ""
  }${hit ? " hit" : ""}${miss ? " miss" : ""}`;
  el.textContent = String(number).padStart(2, "0");
  if (banker) {
    el.title = `${t("banker")} ${number}`;
  } else if (special) {
    el.title = `${t("special")} ${number}`;
  } else {
    el.title = `${t("ball")} ${number}`;
  }
  return el;
}

function renderBalls(container, numbers, special = null, hitSet = null) {
  container.replaceChildren();
  numbers.forEach((num) => {
    const isHit = hitSet ? hitSet.has(num) : false;
    const isMiss = hitSet ? !hitSet.has(num) : false;
    container.appendChild(
      ballElement(num, ballColorFromNumber(num), {
        hit: isHit,
        miss: Boolean(hitSet) && isMiss,
      })
    );
  });
  if (special !== null) {
    container.appendChild(
      ballElement(special, ballColorFromNumber(special), { special: true })
    );
  }
}

function setLoading(loading) {
  isLoading = loading;
  submitBtn.disabled = loading;
  spinner.hidden = !loading;
  if (isBacktest) {
    btnLabel.textContent = loading ? t("backtesting") : t("runBacktest");
  } else {
    btnLabel.textContent = loading ? t("generating") : t("generate");
  }
}

function setLanguage(lang) {
  currentLang = lang === "en" ? "en" : "zh";
  localStorage.setItem("marksix-lang", currentLang);
  applyLanguage();
}

function buildPayload() {
  const draws = Number(drawsInput.value);
  const allHistory = draws >= 1050;
  const payload = {
    strategy: document.getElementById("strategy").value,
    bet_type: betTypeSelect.value,
    draws: allHistory ? 1050 : draws,
    all_history: allHistory,
    pick_count: Number(pickCountInput.value),
    banker_count: Number(bankerCountInput.value),
    trailer_count: Number(trailerCountInput.value),
  };

  if (ticketsInput) {
    payload.tickets = Number(ticketsInput.value);
  }
  if (reviewDrawsInput) {
    payload.review_draws = Number(reviewDrawsInput.value);
  }
  if (showPredictionsInput) {
    payload.show_predictions = Number(showPredictionsInput.value);
  }

  return payload;
}

document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
});

drawsInput.addEventListener("input", () => {
  const value = Number(drawsInput.value);
  drawsValue.textContent = value >= 1050 ? t("drawsAll") : drawsInput.value;
});

if (ticketsInput) {
  ticketsInput.addEventListener("input", () => {
    ticketsValue.textContent = ticketsInput.value;
  });
}

if (reviewDrawsInput) {
  reviewDrawsInput.addEventListener("input", () => {
    reviewValue.textContent = reviewDrawsInput.value;
  });
}

if (showPredictionsInput) {
  showPredictionsInput.addEventListener("input", () => {
    showPredValue.textContent = showPredictionsInput.value;
    if (lastBacktest && isBacktest) {
      renderBacktest(lastBacktest, false);
    }
  });
}

betTypeSelect.addEventListener("change", updateModeFields);
pickCountInput.addEventListener("input", updateHints);
bankerCountInput.addEventListener("input", updateHints);
trailerCountInput.addEventListener("input", updateHints);

updateModeFields();
applyLanguage();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBanner.hidden = true;
  setLoading(true);

  const payload = buildPayload();
  const endpoint = isBacktest ? "/api/backtest" : "/api/generate";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || t("requestFailed"));
    }
    if (isBacktest) {
      renderBacktest(data);
    } else {
      renderResults(data);
    }
  } catch (error) {
    errorBanner.textContent = error.message;
    errorBanner.hidden = false;
  } finally {
    setLoading(false);
  }
});

function renderResults(data, scroll = true) {
  if (!resultsSection) return;
  lastResult = data;
  disclaimer.textContent = t("disclaimer");
  resultsSection.hidden = false;

  document.getElementById("latest-id").textContent = data.latest_draw.draw_id;
  document.getElementById("latest-date").textContent = data.latest_draw.draw_date;
  document.getElementById("draw-count").textContent = t("drawsAnalyzed", {
    n: data.draw_count,
  });

  renderBalls(
    document.getElementById("latest-balls"),
    data.latest_draw.numbers,
    data.latest_draw.special
  );

  const topBody = document.getElementById("top-numbers");
  topBody.replaceChildren();
  data.top_numbers.forEach((item) => {
    const row = document.createElement("tr");
    const ballCell = document.createElement("td");
    ballCell.appendChild(ballElement(item.number, item.color, { small: true }));
    row.appendChild(ballCell);
    ["frequency", "gap", "pair_strength", "composite_score"].forEach((key) => {
      const cell = document.createElement("td");
      cell.textContent = item[key];
      row.appendChild(cell);
    });
    topBody.appendChild(row);
  });

  const label = betLabel(data.bet_type || betTypeSelect.value);
  updateSuggestionsTitle(data.bet_type || betTypeSelect.value);

  const ticketGrid = document.getElementById("ticket-grid");
  ticketGrid.replaceChildren();
  const suggestions = data.suggestions || data.tickets || [];
  suggestions.forEach((ticket, index) => {
    ticketGrid.appendChild(renderSuggestionCard(ticket, index + 1, label));
  });

  if (scroll) {
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderSuggestionCard(ticket, index, label) {
  const card = document.createElement("article");
  card.className = "ticket-card";

  const header = document.createElement("div");
  header.className = "ticket-header";
  const metrics = [
    `${t("scoreLabel")} ${ticket.ticket_score}`,
    `${t("balanceLabel")} ${ticket.balance}`,
  ];
  if (ticket.units != null) {
    metrics.push(`${ticket.units} ${t("units")}`);
    metrics.push(`$${ticket.cost_hkd}`);
  }
  header.innerHTML = `<strong>${label} ${index}</strong><span class="ticket-metrics">${metrics.join(
    " · "
  )}</span>`;
  card.appendChild(header);

  if (ticket.type === "banker") {
    card.appendChild(renderBetGroup(t("banker"), ticket.bankers, { banker: true }));
    card.appendChild(renderBetGroup(t("trailer"), ticket.trailers));
  } else {
    const balls = document.createElement("div");
    balls.className = "ball-row";
    ticket.numbers.forEach((num) => {
      balls.appendChild(ballElement(num, ballColorFromNumber(num), { small: true }));
    });
    if (ticket.special != null) {
      balls.appendChild(
        ballElement(ticket.special, ballColorFromNumber(ticket.special), {
          small: true,
          special: true,
        })
      );
    }
    card.appendChild(balls);
  }

  return card;
}

function renderBetGroup(labelText, numbers, opts = {}) {
  const row = document.createElement("div");
  row.className = "bet-group";
  const label = document.createElement("span");
  label.className = "bet-group-label";
  label.textContent = labelText;
  row.appendChild(label);
  const balls = document.createElement("div");
  balls.className = "ball-row";
  numbers.forEach((num) => {
    balls.appendChild(
      ballElement(num, ballColorFromNumber(num), { small: true, ...opts })
    );
  });
  row.appendChild(balls);
  return row;
}

function summaryCard(label, value, hint = "") {
  const card = document.createElement("div");
  card.className = "summary-card";
  card.innerHTML = `<span class="summary-label">${label}</span><strong class="summary-value">${value}</strong>`;
  if (hint) {
    const hintEl = document.createElement("span");
    hintEl.className = "summary-hint";
    hintEl.textContent = hint;
    card.appendChild(hintEl);
  }
  return card;
}

function renderBacktest(data, scroll = true) {
  if (!backtestSection) return;
  lastBacktest = data;
  disclaimer.textContent = t("disclaimer");
  backtestSection.hidden = false;

  const summary = data.summary;
  const summaryEl = document.getElementById("backtest-summary");
  summaryEl.replaceChildren();
  summaryEl.appendChild(
    summaryCard(t("reviewedDraws", { n: data.review_draws }), betLabel(data.bet_type))
  );
  summaryEl.appendChild(
    summaryCard(
      t("avgHits"),
      String(summary.avg_main_hits),
      `${t("randomBaseline")} ${summary.random_expected_hits}`
    )
  );
  if (summary.avg_best_hits != null) {
    summaryEl.appendChild(
      summaryCard(
        t("avgBestHits"),
        String(summary.avg_best_hits),
        t("bestOfN", {
          n: Number(showPredictionsInput?.value) || data.candidates || 5,
        })
      )
    );
  }
  const vs = summary.vs_random;
  const vsText = vs > 0 ? `+${vs}` : String(vs);
  summaryEl.appendChild(summaryCard(t("vsRandom"), vsText));
  summaryEl.appendChild(
    summaryCard(t("specialHitRate"), `${Math.round(summary.special_hit_rate * 100)}%`)
  );
  summaryEl.appendChild(summaryCard(t("prizeHits"), String(summary.prize_total)));
  summaryEl.appendChild(summaryCard(t("totalCost"), `$${summary.total_cost_hkd}`));

  const dist = document.createElement("div");
  dist.className = "hit-dist";
  dist.innerHTML = `<span class="summary-label">${t("hitDist")}</span>`;
  const bars = document.createElement("div");
  bars.className = "hit-dist-bars";
  Object.entries(summary.hit_distribution).forEach(([hits, count]) => {
    const item = document.createElement("div");
    item.className = "hit-dist-item";
    item.innerHTML = `<span>${hits}</span><strong>${count}</strong>`;
    bars.appendChild(item);
  });
  dist.appendChild(bars);
  summaryEl.appendChild(dist);

  const list = document.getElementById("backtest-list");
  list.replaceChildren();
  data.rows.forEach((row) => {
    list.appendChild(renderBacktestRow(row));
  });

  if (scroll) {
    backtestSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderBacktestRow(row) {
  const card = document.createElement("article");
  card.className = "ticket-card backtest-card";

  const primaryHits = row.comparison.main_hits;
  const bestHits = row.best_comparison?.main_hits ?? primaryHits;
  const hitKey = primaryHits === 1 ? "hitCount" : "hitCountPlural";
  const prize = formatPrize(row.comparison);

  const header = document.createElement("div");
  header.className = "ticket-header";
  const bestNote =
    bestHits > primaryHits ? ` · ${t("bestHits", { n: bestHits })}` : "";
  header.innerHTML = `
    <strong>${row.draw.draw_id} · ${row.draw.draw_date}</strong>
    <span class="ticket-metrics">#1 ${t(hitKey, { n: primaryHits })} · ${prize}${bestNote}</span>`;
  card.appendChild(header);

  const actualHitSet = new Set(row.comparison.hit_numbers);
  const actualLabel = document.createElement("div");
  actualLabel.className = "compare-label";
  actualLabel.textContent = t("actual");
  card.appendChild(actualLabel);
  const actualBalls = document.createElement("div");
  actualBalls.className = "ball-row";
  row.draw.numbers.forEach((num) => {
    actualBalls.appendChild(
      ballElement(num, ballColorFromNumber(num), {
        small: true,
        hit: actualHitSet.has(num),
      })
    );
  });
  actualBalls.appendChild(
    ballElement(row.draw.special, ballColorFromNumber(row.draw.special), {
      small: true,
      special: true,
      hit: row.comparison.special_hit,
    })
  );
  card.appendChild(actualBalls);

  const showCount = Number(showPredictionsInput?.value) || 5;
  const candidates =
    row.candidates && row.candidates.length
      ? row.candidates.slice(0, showCount)
      : [
          {
            rank: 1,
            predicted: row.predicted,
            comparison: row.comparison,
          },
        ];

  candidates.forEach((candidate) => {
    card.appendChild(renderPredictedCandidate(candidate));
  });

  return card;
}

function renderPredictedCandidate(candidate) {
  const wrap = document.createElement("div");
  wrap.className = "predicted-block";

  const hits = candidate.comparison.main_hits;
  const hitKey = hits === 1 ? "hitCount" : "hitCountPlural";
  const prize = formatPrize(candidate.comparison);
  const hitSet = new Set(candidate.comparison.hit_numbers);

  const label = document.createElement("div");
  label.className = "compare-label";
  label.innerHTML = `${t("predictedN", { n: candidate.rank })} <span class="ticket-metrics">${t(
    hitKey,
    { n: hits }
  )} · ${prize}${candidate.comparison.special_hit ? ` · ${t("special")} ✓` : ""}</span>`;
  wrap.appendChild(label);

  const predicted = candidate.predicted;
  if (predicted.type === "banker") {
    const bankerHits = new Set(predicted.bankers.filter((n) => hitSet.has(n)));
    const trailerHits = new Set(predicted.trailers.filter((n) => hitSet.has(n)));
    wrap.appendChild(
      renderCompareGroup(t("banker"), predicted.bankers, bankerHits, { banker: true })
    );
    wrap.appendChild(renderCompareGroup(t("trailer"), predicted.trailers, trailerHits));
  } else {
    const predBalls = document.createElement("div");
    predBalls.className = "ball-row";
    predicted.numbers.forEach((num) => {
      predBalls.appendChild(
        ballElement(num, ballColorFromNumber(num), {
          small: true,
          hit: hitSet.has(num),
          miss: !hitSet.has(num),
        })
      );
    });
    if (predicted.special != null) {
      predBalls.appendChild(
        ballElement(predicted.special, ballColorFromNumber(predicted.special), {
          small: true,
          special: true,
          hit: candidate.comparison.special_hit,
          miss: !candidate.comparison.special_hit,
        })
      );
    }
    wrap.appendChild(predBalls);
  }

  return wrap;
}

function renderCompareGroup(labelText, numbers, hitSet, opts = {}) {
  const row = document.createElement("div");
  row.className = "bet-group";
  const label = document.createElement("span");
  label.className = "bet-group-label";
  label.textContent = labelText;
  row.appendChild(label);
  const balls = document.createElement("div");
  balls.className = "ball-row";
  numbers.forEach((num) => {
    balls.appendChild(
      ballElement(num, ballColorFromNumber(num), {
        small: true,
        hit: hitSet.has(num),
        miss: !hitSet.has(num),
        ...opts,
      })
    );
  });
  row.appendChild(balls);
  return row;
}

function ballColorFromNumber(number) {
  const colorIndex = Math.floor((((number - 1) + Math.floor((number - 1) / 10)) % 6) / 2);
  return ["red", "blue", "green"][colorIndex];
}
