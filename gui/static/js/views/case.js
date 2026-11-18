/**
 * Case View (replaces Alert Detail - The Hero Page)
 * Two-column editorial reading layout:
 * - Left: Narrative summary + 24h timeline rail + raw evidence log.
 * - Right: Why this was flagged (mini-bars), context considered (teal), score composition.
 * - Bottom: Defensible analyst decision form + gated re-identification portal.
 */

import { el, clearNode } from "../dom.js";
import { fetchJson, getSession } from "../api.js";
import { drawTimelineRail, drawScoreCompositionBar } from "../charts.js";

export async function renderCase(container, alertId) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Opening case file...</p></div>`;

  try {
    const data = await fetchJson(`/api/case/${alertId}`);
    renderCaseUI(container, data);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Case file could not be retrieved: ${err.message}</p></div>`;
  }
}

function renderCaseUI(container, caseData) {
  clearNode(container);
  const session = getSession();

  // Header
  const headerBlock = el("div", { class: "page-header-block", style: "border-bottom: 1px solid var(--border-hairline); padding-bottom: var(--space-4);" },
    el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: var(--space-3);" },
      el("div", {},
        el("div", { style: "display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-2);" },
          el("a", { href: "/inbox", class: "btn btn-subtle btn-sm" }, "← Back to Inbox"),
          el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, `Case File ID: ${caseData.alert_id.slice(0, 8)}…`)
        ),
        el("h1", {}, `Case Review: ${caseData.pseudonym}`),
        el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
          `Role: ${caseData.role} • Dept: ${caseData.department} • Location: ${caseData.home_city}, ${caseData.home_country} • Status: `,
          el("strong", {}, caseData.status.toUpperCase())
        )
      ),
      el("div", { style: "text-align: right;" },
        el("div", { class: "score-numeral-lg" }, Math.round(caseData.risk_score)),
        el("div", { class: `severity-mark severity-${caseData.severity_band}`, style: "justify-content: flex-end;" },
          el("span", { class: "mark-symbol" }),
          el("span", {}, `${caseData.severity_band.toUpperCase()} SEVERITY`)
        )
      )
    )
  );
  container.appendChild(headerBlock);

  // Two-Column Editorial Grid
  const grid = el("div", { class: "editorial-grid-2", style: "margin-top: var(--space-6);" });

  // --- LEFT COLUMN (Narrative + Timeline + Evidence Log) ---
  const leftCol = el("div");

  // Editorial Narrative Card
  const narrativeCard = el("div", { class: "editorial-card" });
  narrativeCard.appendChild(el("h3", { style: "margin-bottom: var(--space-3);" }, "Incident Briefing"));
  narrativeCard.appendChild(el("p", { class: "serif-prose" }, caseData.narrative));
  leftCol.appendChild(narrativeCard);

  // 24-Hour Timeline Rail Card
  const timelineCard = el("div", { class: "editorial-card" });
  timelineCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "Day Timeline Rail"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, `${caseData.alert_date} (UTC)`)
  ));

  const railWrapper = el("div", { class: "timeline-rail-container" });
  drawTimelineRail(
    railWrapper,
    caseData.timeline_events || [],
    caseData.work_start_hour || 9,
    caseData.work_end_hour || 17,
    (ev) => highlightEventInTable(ev.event_id)
  );
  timelineCard.appendChild(railWrapper);

  // Raw Event Log Table
  timelineCard.appendChild(el("h4", { style: "margin: var(--space-4) 0 var(--space-2);" }, "Recorded Telemetry"));
  const evTable = el("table", { class: "ledger-table", style: "font-size: var(--text-xs);" });
  evTable.innerHTML = `
    <thead>
      <tr>
        <th style="width: 70px;">Type</th>
        <th style="width: 90px;">Time (UTC)</th>
        <th>Event Details</th>
        <th style="width: 100px;">Evidence Flag</th>
      </tr>
    </thead>
  `;
  const evTbody = el("tbody");
  (caseData.timeline_events || []).forEach((ev) => {
    const tr = el("tr", { id: `ev-row-${ev.event_id}` });
    if (ev.is_evidence) {
      tr.style.backgroundColor = "var(--bg-subtle)";
    }
    tr.appendChild(el("td", { class: "text-mono" }, ev.type.toUpperCase()));
    tr.appendChild(el("td", { class: "text-mono text-muted" }, ev.timestamp.slice(11, 19)));
    tr.appendChild(el("td", {}, ev.description));
    tr.appendChild(el("td", { class: "text-mono" },
      ev.is_evidence
        ? el("span", { style: "color: var(--accent-vermilion); font-weight: 600;" }, "CRITICAL EVIDENCE")
        : el("span", { class: "text-muted" }, "Background")
    ));
    evTbody.appendChild(tr);
  });
  evTable.appendChild(evTbody);
  timelineCard.appendChild(evTable);

  leftCol.appendChild(timelineCard);
  grid.appendChild(leftCol);

  // --- RIGHT COLUMN (Why This Was Flagged + Context Applied + Composition) ---
  const rightCol = el("div");

  // Why This Was Flagged Card
  const whyCard = el("div", { class: "editorial-card" });
  whyCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "Why This Was Flagged"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, `${caseData.indicators.length} signals`)
  ));

  const indList = el("div", { style: "display: flex; flex-direction: column; gap: var(--space-4);" });
  caseData.indicators.forEach((ind, i) => {
    const indItem = el("div", {
      style: "border-bottom: 1px solid var(--border-hairline); padding-bottom: var(--space-3);",
    });

    // Title + Points
    const indHeader = el("div", { style: "display: flex; justify-content: space-between; align-items: baseline;" },
      el("strong", { style: "font-size: var(--text-sm);" }, `${i + 1}. ${ind.name.replace(/_/g, " ")}`),
      el("span", { class: "text-mono", style: "font-weight: 600; font-size: var(--text-sm);" }, `+${(ind.severity_points || 0).toFixed(1)} pts`)
    );
    indItem.appendChild(indHeader);

    // Description
    indItem.appendChild(el("p", { class: "text-muted", style: "font-size: var(--text-xs); margin: 4px 0;" }, ind.description));

    // Mini bar pair (Observed vs Usual)
    if (ind.baseline_value !== undefined && ind.observed_value !== undefined) {
      const barBox = el("div", { style: "margin: 6px 0;" });
      const barLabels = el("div", {
        style: "display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);",
      },
        el("span", {}, `Usual: ${formatVal(ind.baseline_value)}`),
        el("span", { style: "color: var(--accent-vermilion); font-weight: 500;" }, `Observed: ${formatVal(ind.observed_value)}`)
      );
      barBox.appendChild(barLabels);
      indItem.appendChild(barBox);
    }

    // Why it matters
    if (ind.why_it_matters) {
      indItem.appendChild(el("p", {
        style: "font-size: 11px; font-style: italic; color: var(--text-dim); margin-top: 4px;",
      }, ind.why_it_matters));
    }

    indList.appendChild(indItem);
  });
  whyCard.appendChild(indList);
  rightCol.appendChild(whyCard);

  // Context Considered Block (Deep Teal Accent)
  const contextBox = el("div", { class: "editorial-card" });
  contextBox.appendChild(el("h4", { style: "color: var(--accent-teal); margin-bottom: var(--space-2);" }, "Business Context Considered"));

  if (caseData.context_applied && caseData.context_applied.length > 0) {
    caseData.context_applied.forEach((ctx) => {
      const callout = el("div", { class: "context-callout" },
        el("strong", {}, `Approved: ${ctx.context_type.replace(/_/g, " ").toUpperCase()}`),
        el("p", { style: "margin-top: 4px;" },
          `Sign-off by ${ctx.approved_by || "Management"}. Moderated score by ${Math.round((ctx.reduction_factor || 0) * 100)}%.`
        )
      );
      contextBox.appendChild(callout);
    });
  } else {
    contextBox.appendChild(el("div", { class: "context-callout" },
      el("strong", {}, "No Approved Context Found"),
      el("p", { style: "margin-top: 4px;" },
        "The calendar and roster verified no prior approved travel, on-call window, or maintenance schedule for this timeframe."
      )
    ));
  }
  rightCol.appendChild(contextBox);

  // Score Composition Bar
  const compCard = el("div", { class: "editorial-card" });
  compCard.appendChild(el("h4", { style: "margin-bottom: var(--space-2);" }, "Score Composition"));
  drawScoreCompositionBar(
    compCard,
    caseData.indicators,
    caseData.chain_bonuses || [],
    caseData.context_applied || [],
    caseData.risk_score
  );
  rightCol.appendChild(compCard);

  // Gated Re-Identification Box
  const reidCard = el("div", { class: "editorial-card" });
  reidCard.appendChild(el("h4", { style: "margin-bottom: var(--space-2);" }, "Identity Safeguards"));
  reidCard.appendChild(el("p", { class: "text-muted", style: "font-size: var(--text-xs);" },
    "Under data minimization principles, identity is masked as " + caseData.pseudonym + ". Re-identification is restricted to Senior Analysts with audited written justification."
  ));

  const reidBtn = el("button", {
    class: "btn btn-sm",
    style: "margin-top: var(--space-3); width: 100%;",
    onclick: () => openReidentificationModal(caseData.pseudonym),
  }, "Request Re-Identification");
  reidCard.appendChild(reidBtn);
  rightCol.appendChild(reidCard);

  grid.appendChild(rightCol);
  container.appendChild(grid);

  // --- BOTTOM SECTION: Analyst Decision Form ---
  const decisionCard = el("div", { class: "editorial-card", id: "feedback-form-container", style: "margin-top: var(--space-8);" });
  decisionCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "Analyst Review & Verdict"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs); font-style: italic;" }, "An anomaly is not proof of wrongdoing.")
  ));

  const form = el("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      await submitDecision(caseData.alert_id, container);
    },
  });

  form.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: var(--space-6);">
      <div>
        <label style="display: block; font-size: var(--text-sm); font-weight: 500; margin-bottom: 6px;">Verdict</label>
        <select id="verdict-select" style="width: 100%;">
          <option value="needs_more_info">Needs More Info (Pending Review)</option>
          <option value="benign_expected">Benign Expected (Legitimate Activity)</option>
          <option value="false_positive">False Positive (Suppression Rule)</option>
          <option value="confirmed_suspicious">Confirmed Suspicious (Escalate)</option>
        </select>

        <div style="margin-top: var(--space-4);">
          <label style="display: flex; align-items: center; gap: 8px; font-size: var(--text-xs); cursor: pointer;">
            <input type="checkbox" id="create-rule-check" />
            <span>Create 30-day dampening adjustment rule</span>
          </label>
        </div>
      </div>

      <div>
        <label style="display: block; font-size: var(--text-sm); font-weight: 500; margin-bottom: 6px;">Review Notes (max 500 chars)</label>
        <textarea id="notes-textarea" rows="4" style="width: 100%; resize: vertical;" placeholder="Document your analytical reasoning and corroborating evidence…"></textarea>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: var(--space-3);">
          <span id="form-msg" style="font-size: var(--text-xs); color: var(--text-muted);"></span>
          <button type="submit" class="btn btn-primary" id="btn-submit-verdict">Record Decision</button>
        </div>
      </div>
    </div>
  `;

  decisionCard.appendChild(form);
  container.appendChild(decisionCard);
}

function formatVal(v) {
  if (typeof v === "number") {
    if (v > 1000000) return `${(v / (1024 * 1024)).toFixed(1)} MB`;
    return String(Math.round(v));
  }
  if (Array.isArray(v)) return v.join(", ") || "none";
  return String(v);
}

function highlightEventInTable(eid) {
  const row = document.getElementById(`ev-row-${eid}`);
  if (row) {
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    row.style.outline = "2px solid var(--accent-vermilion)";
    setTimeout(() => {
      row.style.outline = "";
    }, 2000);
  }
}

async function submitDecision(alertId, container) {
  const verdict = document.getElementById("verdict-select")?.value;
  const notes = document.getElementById("notes-textarea")?.value || "";
  const createRule = document.getElementById("create-rule-check")?.checked || false;
  const msgEl = document.getElementById("form-msg");
  const submitBtn = document.getElementById("btn-submit-verdict");

  if (!verdict) return;

  if (submitBtn) submitBtn.disabled = true;
  if (msgEl) msgEl.textContent = "Committing to audit ledger…";

  try {
    const res = await fetchJson(`/api/case/${alertId}/feedback`, {
      method: "POST",
      body: JSON.stringify({
        verdict,
        notes,
        create_rule: createRule,
        rule_days: 30,
      }),
    });

    if (msgEl) {
      msgEl.textContent = "Verdict recorded and committed to tamper-evident audit ledger.";
      msgEl.style.color = "var(--accent-teal)";
    }
    setTimeout(() => {
      renderCase(container, alertId);
    }, 1200);
  } catch (err) {
    if (msgEl) {
      msgEl.textContent = err.message;
      msgEl.style.color = "var(--accent-vermilion)";
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function openReidentificationModal(pseudonym) {
  const session = getSession();
  if (session.role !== "senior_analyst") {
    alert("Permission Denied: Identity re-identification requires the 'senior_analyst' role. Please switch personas in the top header.");
    return;
  }

  const reason = prompt(`[GATED ACCESS] Enter mandatory justification to unmask ${pseudonym} (minimum 20 characters, fully audited):`);
  if (!reason) return;

  if (reason.trim().length < 20) {
    alert("Error: Justification must be at least 20 characters in length.");
    return;
  }

  fetchJson("/api/case/reidentify", {
    method: "POST",
    body: JSON.stringify({
      pseudonym_id: pseudonym,
      reason: reason.trim(),
    }),
  })
    .then((res) => {
      alert(`RE-IDENTIFICATION RESULT:\nPseudonym: ${pseudonym}\nInternal Employee ID: ${res.real_user_id}\n\nNotice: This action has been permanently committed to the SHA-256 cryptographic audit ledger.`);
    })
    .catch((err) => {
      alert(`Re-identification failed: ${err.message}`);
    });
}

