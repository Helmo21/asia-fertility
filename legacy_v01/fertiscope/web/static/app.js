// FertiScope local web UI - multi-turn conversation mode.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => root.querySelectorAll(sel);

const turnsListEl = $("#turns-list");
const turnRowTpl = $("#turn-row-template");
const convoReportTpl = $("#convo-report-template");
const tokenizerListEl = $("#tokenizer-list");
const analyzeBtn = $("#analyze-btn");
const statusEl = $("#status");
const resultsEl = $("#results");

let availableTokenizers = [];
let lastReports = {};   // tokenizer_id -> serialized report (after Analyze)
let lastTurns = 0;       // number of turns in the last analysis (for status messages)

function setStatus(msg, kind = "") {
  statusEl.textContent = msg;
  statusEl.className = "status " + kind;
}

function renumberTurns() {
  const rows = $$(".turn-row", turnsListEl);
  rows.forEach((row, i) => {
    $(".turn-number", row).textContent = `Turn ${i + 1}`;
  });
}

function addTurnRow({ role = "user", en = "", vi = "" } = {}) {
  const frag = turnRowTpl.content.cloneNode(true);
  const row = frag.querySelector(".turn-row");
  $(".role-select", row).value = role;
  $(".en-text", row).value = en;
  $(".vi-text", row).value = vi;
  $(".remove-turn", row).addEventListener("click", () => {
    row.remove();
    renumberTurns();
    if ($$(".turn-row").length === 0) addTurnRow();
  });
  turnsListEl.appendChild(row);
  renumberTurns();
}

async function loadTokenizers() {
  const res = await fetch("/api/tokenizers");
  const data = await res.json();
  availableTokenizers = data.tokenizers;
  tokenizerListEl.innerHTML = "";
  availableTokenizers.forEach((tok, idx) => {
    const label = document.createElement("label");
    label.innerHTML = `
      <input type="radio" name="tokenizer" value="${tok.id}" ${idx === 0 ? "checked" : ""}>
      <span>
        <span class="name">${tok.display_name}</span>
        <span class="note">${tok.notes}</span>
      </span>
    `;
    tokenizerListEl.appendChild(label);
  });
  // Wire radio change events: switching tokenizer re-renders from cache, no API call.
  $$("#tokenizer-list input[type=radio]").forEach((r) => {
    r.addEventListener("change", renderSelectedReport);
  });
}

function renderSelectedReport() {
  const ids = selectedTokenizerIds();
  if (!ids.length) return;
  const id = ids[0];
  const report = lastReports[id];
  resultsEl.innerHTML = "";
  if (!report) {
    // No analysis has been run yet - show a gentle nudge
    const div = document.createElement("div");
    div.className = "card hint-card";
    div.innerHTML = `<p class="hint">No analysis cached yet. Click <strong>Analyze conversation</strong> to compute results for all tokenizers, then switch between them with the radios above.</p>`;
    resultsEl.appendChild(div);
    return;
  }
  resultsEl.appendChild(renderConvoReport(report));
  setStatus(`Showing ${report.tokenizer_display} (${lastTurns} turns analyzed)`, "success");
}

async function loadFlores() {
  setStatus("Loading FLORES-200 sample (1 turn)...", "");
  const res = await fetch("/api/flores-sample");
  const data = await res.json();
  turnsListEl.innerHTML = "";
  addTurnRow({ role: "user", en: data.en, vi: data.vi });
  setStatus(`Loaded ${data.sentence_count} FLORES sentence pairs as 1 user turn`, "success");
}

function loadConvoSample() {
  // A small handcrafted 5-turn parallel conversation (customer support style).
  turnsListEl.innerHTML = "";
  const convo = [
    { role: "system",
      en: "You are a helpful customer support agent for a Southeast Asian e-commerce platform. Be concise and friendly.",
      vi: "Bạn là một nhân viên hỗ trợ khách hàng hữu ích cho một nền tảng thương mại điện tử Đông Nam Á. Hãy ngắn gọn và thân thiện." },
    { role: "user",
      en: "Hi, I ordered three items last week but only received two of them. Can you help me find the third one?",
      vi: "Chào bạn, tuần trước tôi đã đặt ba món đồ nhưng chỉ nhận được hai. Bạn có thể giúp tôi tìm món thứ ba được không?" },
    { role: "assistant",
      en: "Of course! Could you please share your order number so I can look into this for you?",
      vi: "Tất nhiên rồi! Bạn có thể chia sẻ số đơn hàng để tôi có thể kiểm tra giúp bạn không?" },
    { role: "user",
      en: "The order number is VN-2026-77831. The missing item is a blue ceramic mug.",
      vi: "Số đơn hàng là VN-2026-77831. Món bị thiếu là một chiếc cốc sứ màu xanh." },
    { role: "assistant",
      en: "Thanks. I can see the mug was held back due to a packaging defect found in the warehouse. We're shipping a replacement today and you should receive it within two business days. I've added a small credit to your account as an apology.",
      vi: "Cảm ơn bạn. Tôi thấy rằng chiếc cốc đã bị giữ lại do phát hiện lỗi đóng gói tại kho. Chúng tôi sẽ gửi một sản phẩm thay thế ngay hôm nay và bạn sẽ nhận được trong vòng hai ngày làm việc. Tôi cũng đã thêm một khoản tín dụng nhỏ vào tài khoản của bạn như một lời xin lỗi." },
  ];
  for (const t of convo) addTurnRow(t);
  setStatus(`Loaded a 5-turn customer-support conversation`, "success");
}

function clearAll() {
  turnsListEl.innerHTML = "";
  addTurnRow();
  resultsEl.innerHTML = "";
  lastReports = {};
  lastTurns = 0;
  setStatus("", "");
}

function collectTurns() {
  const rows = $$(".turn-row", turnsListEl);
  const turns = [];
  for (const row of rows) {
    const role = $(".role-select", row).value;
    const en = $(".en-text", row).value.trim();
    const vi = $(".vi-text", row).value.trim();
    if (!en && !vi) continue;
    turns.push({ role, en, vi });
  }
  return turns;
}

function selectedTokenizerIds() {
  // Single-select via radio - returns a 1-element array (backend still accepts a list).
  const checked = $("#tokenizer-list input[type=radio]:checked");
  return checked ? [checked.value] : [];
}

function ratioClass(ratio) {
  if (ratio < 1.3) return "low";
  if (ratio < 2.0) return "mid";
  return "high";
}

function formatOverflow(turn, totalTurns) {
  if (turn === 0) return `never (in ${totalTurns} turns)`;
  return `turn ${turn}`;
}

function pickCheapestPrice(prices) {
  // Cheapest input-tokens price row that has nonzero pricing. Returns null if none.
  const positive = prices.filter((p) => p.input_per_1m_usd > 0);
  if (!positive.length) return null;
  return positive.reduce((a, b) => (a.input_per_1m_usd <= b.input_per_1m_usd ? a : b));
}

function formatUsd(x) {
  if (x === 0) return "$0";
  if (x < 0.000001) return "<$0.000001";
  return "$" + x.toFixed(6);
}

function renderTokenChart(container, turns, projection, en4096 = 4096, en8192 = 8192) {
  // Hand-rolled SVG line chart. Solid series for entered turns + dashed series
  // for the linear-extrapolation projection. Two dashed horizontal refs at
  // 4096 and 8192 token budgets.
  const W = 660, H = 280;
  const M = { top: 14, right: 18, bottom: 30, left: 56 };
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const n = turns.length;
  const lastEnteredTurnIndex = n > 0 ? turns[n - 1].turn_index : 0;
  const projLast = projection.length > 0
    ? projection[projection.length - 1].turn_index
    : lastEnteredTurnIndex;
  const maxTurnIndex = Math.max(lastEnteredTurnIndex, projLast, 1);

  const allEn = [...turns.map(t => t.cumulative_en_tokens), ...projection.map(p => p.cumulative_en_tokens)];
  const allVi = [...turns.map(t => t.cumulative_vi_tokens), ...projection.map(p => p.cumulative_vi_tokens)];
  const maxCum = Math.max(en8192, ...allEn, ...allVi);
  const yMax = Math.max(en8192, Math.ceil(maxCum / 1024) * 1024);

  const x = (turnIdx) => M.left + ((turnIdx - 1) / Math.max(maxTurnIndex - 1, 1)) * innerW;
  const y = (v) => M.top + innerH - (v / yMax) * innerH;

  const enSolidPath = turns.map((t, i) => `${i === 0 ? "M" : "L"}${x(t.turn_index)},${y(t.cumulative_en_tokens)}`).join(" ");
  const viSolidPath = turns.map((t, i) => `${i === 0 ? "M" : "L"}${x(t.turn_index)},${y(t.cumulative_vi_tokens)}`).join(" ");

  // Dashed projection paths START at the last entered turn so the dashed line
  // visually connects to the solid line.
  const enDashedPath = (n > 0 && projection.length > 0)
    ? `M${x(turns[n-1].turn_index)},${y(turns[n-1].cumulative_en_tokens)} ` +
      projection.map(p => `L${x(p.turn_index)},${y(p.cumulative_en_tokens)}`).join(" ")
    : "";
  const viDashedPath = (n > 0 && projection.length > 0)
    ? `M${x(turns[n-1].turn_index)},${y(turns[n-1].cumulative_vi_tokens)} ` +
      projection.map(p => `L${x(p.turn_index)},${y(p.cumulative_vi_tokens)}`).join(" ")
    : "";

  const yTicks = [0, en4096, en8192];
  if (yMax > en8192) yTicks.push(yMax);

  // X ticks: include 1, last entered, and projection end, plus a few in between
  const xTickValues = new Set([1, lastEnteredTurnIndex]);
  if (projLast > lastEnteredTurnIndex) xTickValues.add(projLast);
  // intermediate ticks
  const stride = Math.max(1, Math.floor(maxTurnIndex / 8));
  for (let i = 1; i <= maxTurnIndex; i += stride) xTickValues.add(i);
  const xTicks = [...xTickValues].sort((a, b) => a - b);

  const yTickElems = yTicks.map((v) => `
    <line class="grid-line" x1="${M.left}" x2="${W - M.right}" y1="${y(v)}" y2="${y(v)}"></line>
    <text x="${M.left - 8}" y="${y(v) + 3}" text-anchor="end">${v.toLocaleString()}</text>
  `).join("");

  const xTickElems = xTicks.map((t) => `
    <text x="${x(t)}" y="${H - M.bottom + 16}" text-anchor="middle">T${t}</text>
  `).join("");

  // Boundary marker between entered and projected ranges
  const boundaryX = x(lastEnteredTurnIndex + 0.5);
  const boundaryMarker = projection.length > 0 ? `
    <line class="boundary-line" x1="${boundaryX}" x2="${boundaryX}" y1="${M.top}" y2="${H - M.bottom}" stroke="var(--muted)" stroke-dasharray="2 3" stroke-width="1" opacity="0.5"></line>
    <text class="boundary-label" x="${boundaryX}" y="${M.top + 10}" text-anchor="middle" fill="var(--muted)" font-size="9">entered \u2192 projected</text>
  ` : "";

  const dotsEntered = turns.map((t) =>
    `<circle class="dot-en" cx="${x(t.turn_index)}" cy="${y(t.cumulative_en_tokens)}" r="3"></circle>
     <circle class="dot-vi" cx="${x(t.turn_index)}" cy="${y(t.cumulative_vi_tokens)}" r="3"></circle>`
  ).join("");

  // Smaller markers on the projected points
  const dotsProjected = projection.map((p) =>
    `<circle class="dot-en" cx="${x(p.turn_index)}" cy="${y(p.cumulative_en_tokens)}" r="1.5" opacity="0.7"></circle>
     <circle class="dot-vi" cx="${x(p.turn_index)}" cy="${y(p.cumulative_vi_tokens)}" r="1.5" opacity="0.7"></circle>`
  ).join("");

  const refLine = (v, cls, label) => v <= yMax ? `
    <line class="ref-line ${cls}" x1="${M.left}" x2="${W - M.right}" y1="${y(v)}" y2="${y(v)}"></line>
    <text class="ref-label" x="${W - M.right - 4}" y="${y(v) - 4}" text-anchor="end">${label}</text>
  ` : "";

  const svg = `
    <div class="legend">
      <span><span class="swatch sw-en"></span>EN cumulative</span>
      <span><span class="swatch sw-vi"></span>VI cumulative</span>
      <span><span class="swatch sw-en-dashed"></span>EN projected</span>
      <span><span class="swatch sw-vi-dashed"></span>VI projected</span>
      <span><span class="swatch sw-ref-4096"></span>4096 limit</span>
      <span><span class="swatch sw-ref-8192"></span>8192 limit</span>
    </div>
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      <g class="axis">
        <line x1="${M.left}" y1="${M.top}" x2="${M.left}" y2="${H - M.bottom}"></line>
        <line x1="${M.left}" y1="${H - M.bottom}" x2="${W - M.right}" y2="${H - M.bottom}"></line>
        ${yTickElems}
        ${xTickElems}
      </g>
      ${refLine(en4096, "ref-line-4096", "4096")}
      ${refLine(en8192, "ref-line-8192", "8192")}
      ${boundaryMarker}
      <path class="line-en" d="${enSolidPath}"></path>
      <path class="line-vi" d="${viSolidPath}"></path>
      <path class="line-en-dashed" d="${enDashedPath}"></path>
      <path class="line-vi-dashed" d="${viDashedPath}"></path>
      ${dotsEntered}
      ${dotsProjected}
    </svg>
  `;
  container.innerHTML = svg;
}

function renderConvoReport(report) {
  const node = convoReportTpl.content.cloneNode(true);
  node.querySelector(".tokenizer-name").textContent = report.tokenizer_display;

  const ratioCls = ratioClass(report.fertility_ratio);
  const badge = node.querySelector(".ratio-badge");
  badge.textContent = `VI = ${report.fertility_ratio.toFixed(2)}x EN`;
  badge.classList.add(ratioCls);

  node.querySelector(".en-total").textContent = report.total_en_tokens.toLocaleString();
  node.querySelector(".vi-total").textContent = report.total_vi_tokens.toLocaleString();
  node.querySelector(".ratio-val").textContent = `${report.fertility_ratio.toFixed(2)}x`;

  const n = report.turns.length;
  const o4 = node.querySelector(".overflow-4096");
  o4.textContent = formatOverflow(report.first_overflow_turn_4096, n);
  if (report.first_overflow_turn_4096 > 0) o4.classList.add("danger");

  const o8 = node.querySelector(".overflow-8192");
  o8.textContent = formatOverflow(report.first_overflow_turn_8192, n);
  if (report.first_overflow_turn_8192 > 0) o8.classList.add("danger");

  // Pick the cheapest provider price for per-turn $ column
  const cheapest = pickCheapestPrice(report.prices);
  const providerTag = node.querySelector(".provider-tag");
  if (cheapest) {
    providerTag.textContent = `(${cheapest.provider} ${cheapest.model} @ $${cheapest.input_per_1m_usd}/1M tokens)`;
  } else {
    providerTag.textContent = "(no public pricing available; per-turn $ shown as —)";
  }

  const tbody = node.querySelector(".turns-body");
  for (const t of report.turns) {
    const tr = document.createElement("tr");
    const overflow4 = t.cumulative_pct_4096 >= 100 ? "danger" : (t.cumulative_pct_4096 >= 80 ? "warn" : "");
    const overflow8 = t.cumulative_pct_8192 >= 100 ? "danger" : (t.cumulative_pct_8192 >= 80 ? "warn" : "");
    const enTurnCost = cheapest ? cheapest.input_per_1m_usd * t.en_tokens / 1_000_000 : null;
    const viTurnCost = cheapest ? cheapest.input_per_1m_usd * t.vi_tokens / 1_000_000 : null;
    tr.innerHTML = `
      <td>${t.turn_index}</td>
      <td class="role-${t.role}">${t.role}</td>
      <td>${t.en_tokens.toLocaleString()}</td>
      <td>${t.vi_tokens.toLocaleString()}</td>
      <td>${t.cumulative_en_tokens.toLocaleString()}</td>
      <td>${t.cumulative_vi_tokens.toLocaleString()}</td>
      <td class="cost-col">${enTurnCost === null ? "—" : formatUsd(enTurnCost)}</td>
      <td class="cost-col">${viTurnCost === null ? "—" : formatUsd(viTurnCost)}</td>
      <td class="${overflow4}">${t.cumulative_pct_4096.toFixed(1)}%</td>
      <td class="${overflow8}">${t.cumulative_pct_8192.toFixed(1)}%</td>
    `;
    tbody.appendChild(tr);
  }

  // Render projection strip cells
  const slopeEnEl = node.querySelector(".slope-en");
  const slopeViEl = node.querySelector(".slope-vi");
  const pred4 = node.querySelector(".pred-4096");
  const pred8 = node.querySelector(".pred-8192");
  const horizonEl = node.querySelector(".proj-horizon");

  if (report.turns.length < 2) {
    slopeEnEl.textContent = "—";
    slopeViEl.textContent = "—";
    pred4.textContent = "need ≥2 turns";
    pred8.textContent = "need ≥2 turns";
    horizonEl.textContent = "—";
  } else {
    slopeEnEl.textContent = `${report.projected_slope_en.toFixed(1)} tok/turn`;
    slopeViEl.textContent = `${report.projected_slope_vi.toFixed(1)} tok/turn`;
    pred4.textContent = report.predicted_overflow_turn_4096 > 0
      ? `turn ${report.predicted_overflow_turn_4096}`
      : "out of range";
    if (report.predicted_overflow_turn_4096 > 0) pred4.classList.add("danger");
    pred8.textContent = report.predicted_overflow_turn_8192 > 0
      ? `turn ${report.predicted_overflow_turn_8192}`
      : "out of range";
    if (report.predicted_overflow_turn_8192 > 0) pred8.classList.add("danger");
    const lastProj = report.projection.length
      ? report.projection[report.projection.length - 1].turn_index
      : report.turns[report.turns.length - 1].turn_index;
    horizonEl.textContent = `T${lastProj}`;
  }

  // Render the cumulative-tokens line chart (with extrapolation if available)
  const chartContainer = node.querySelector(".chart-wrap");
  renderTokenChart(chartContainer, report.turns, report.projection || []);

  const pricesBody = node.querySelector(".prices-body");
  if (!report.prices.length) {
    pricesBody.innerHTML = `<tr><td colspan="6" style="color: var(--muted); text-align: center;">No public pricing for this tokenizer family yet.</td></tr>`;
  } else {
    for (const p of report.prices) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${p.provider}</td>
        <td>${p.model}</td>
        <td>$${p.per_corpus_en_usd.toFixed(6)}</td>
        <td>$${p.per_corpus_vi_usd.toFixed(6)}</td>
        <td>$${p.stateless_en_usd.toFixed(6)}</td>
        <td class="bold">$${p.stateless_vi_usd.toFixed(6)}</td>
      `;
      pricesBody.appendChild(tr);
    }
  }

  return node;
}

async function runAnalysis() {
  const turns = collectTurns();
  if (turns.length === 0) {
    setStatus("Add at least one turn with text (EN or VI).", "error");
    return;
  }
  // Always compute ALL tokenizers so the user can switch between them instantly
  // without re-analyzing. The visible card is whichever radio is selected.
  const allTokenizerIds = availableTokenizers.map((t) => t.id);
  analyzeBtn.disabled = true;
  setStatus(`Analyzing ${turns.length} turn(s) across ${allTokenizerIds.length} tokenizers...`, "");
  try {
    const res = await fetch("/api/analyze-conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ turns, tokenizers: allTokenizerIds }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    // Cache reports keyed by tokenizer id so radio clicks render instantly
    lastReports = {};
    for (const r of data.reports) lastReports[r.tokenizer_id] = r;
    lastTurns = turns.length;

    // Show the currently-selected tokenizer's report
    renderSelectedReport();

    // Append any backend errors below
    for (const err of data.errors) {
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `<strong>${err.tokenizer_id} failed:</strong> ${err.error}`;
      resultsEl.appendChild(div);
    }
  } catch (e) {
    setStatus(`Error: ${e.message}`, "error");
  } finally {
    analyzeBtn.disabled = false;
  }
}

// Init
$("#add-turn").addEventListener("click", () => addTurnRow());
$("#load-flores").addEventListener("click", loadFlores);
$("#load-convo").addEventListener("click", loadConvoSample);
$("#clear-text").addEventListener("click", clearAll);
$("#analyze-btn").addEventListener("click", runAnalysis);

addTurnRow();  // start with one empty user turn
loadTokenizers().then(() => {
  // ?auto=convo loads the 5-turn sample and triggers Analyze automatically.
  // Used by headless-Chrome screenshots and lets you bookmark a demo URL.
  const params = new URLSearchParams(window.location.search);
  if (params.get("auto") === "convo") {
    loadConvoSample();
    setTimeout(() => runAnalysis(), 600);
  }
}).catch((e) => setStatus(`Failed to load tokenizers: ${e.message}`, "error"));
