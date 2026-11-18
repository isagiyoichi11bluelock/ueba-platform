/**
 * Normal View (replaces Baselines)
 * "What normal looks like for this person and for their role."
 * Side-by-side small multiples, confidence meter bar, and cold-start blending dynamics.
 */

import { el, clearNode } from "../dom.js";
import { fetchJson } from "../api.js";

export async function renderNormal(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading baseline comparisons...</p></div>`;

  try {
    const pData = await fetchJson("/api/people");
    const people = pData.people || [];

    if (people.length === 0) {
      container.innerHTML = `<div class="attention-callout"><p>No accounts found in database.</p></div>`;
      return;
    }

    renderNormalUI(container, people);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load baselines: ${err.message}</p></div>`;
  }
}

function renderNormalUI(container, people) {
  clearNode(container);

  // Header
  const headerBlock = el("div", { class: "page-header-block" },
    el("h1", {}, "What Normal Looks Like"),
    el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
      "Behavioral baselines profile what is customary for an individual versus their departmental peers."
    )
  );
  container.appendChild(headerBlock);

  // Identity Picker
  const picker = el("div", {
    class: "editorial-card",
    style: "display: flex; align-items: center; gap: var(--space-4); margin-bottom: var(--space-6);",
  },
    el("label", { style: "font-size: var(--text-sm); font-weight: 500;" }, "Account to Examine:"),
    el("select", {
      style: "min-width: 320px;",
      onchange: (e) => loadBaselineContent(e.target.value, baselineContent),
    },
      ...people.map((p, idx) => {
        const opt = el("option", { value: p.user_id }, `${p.pseudonym} — ${p.role} (${p.department})`);
        if (idx === 0) opt.selected = true;
        return opt;
      })
    )
  );
  container.appendChild(picker);

  const baselineContent = el("div", { id: "normal-content-container" });
  container.appendChild(baselineContent);

  if (people.length > 0) {
    loadBaselineContent(people[0].user_id, baselineContent);
  }
}

async function loadBaselineContent(userId, container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-6); text-align: center;"><p class="text-muted">Loading baseline metrics…</p></div>`;

  try {
    const data = await fetchJson(`/api/normal/${userId}`);
    clearNode(container);

    // Confidence & Cold-Start Explanation Card
    const confCard = el("div", { class: "editorial-card" });
    confCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, `Baseline Confidence: ${Math.round(data.confidence * 100)}%`),
      el("span", { class: "text-mono text-muted", style: "font-size: var(--text-xs);" }, `Subject: ${data.pseudonym} (${data.role})`)
    ));

    // Thin Meter Bar
    const meterWrapper = el("div", { style: "margin: var(--space-3) 0;" },
      el("div", {
        style: "height: 6px; width: 100%; background: var(--bg-subtle); border-radius: 1px; overflow: hidden; border: 1px solid var(--border-hairline);",
      },
        el("div", {
          style: `height: 100%; width: ${Math.round(data.confidence * 100)}%; background: ${data.is_cold_start ? "var(--accent-vermilion)" : "var(--text-main)"};`,
        })
      ),
      el("div", {
        style: "display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 4px;",
      },
        el("span", {}, "0% (Pure Peer Reference)"),
        el("span", {}, "100% (Full Personal Baseline)")
      )
    );
    confCard.appendChild(meterWrapper);

    // Written Cold-Start Narrative
    confCard.appendChild(el("p", { class: "serif-prose", style: "margin-top: var(--space-3);" }, data.explanation));
    container.appendChild(confCard);

    // Side-by-side comparison table
    const compCard = el("div", { class: "editorial-card" });
    compCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Individual Baseline vs Departmental Peer Norms"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, `Peer Group: ${data.role}`)
    ));

    const uBl = data.user_baseline || {};
    const rBl = data.role_baseline || {};

    const table = el("table", { class: "ledger-table" });
    table.innerHTML = `
      <thead>
        <tr>
          <th>Metric Domain</th>
          <th style="text-align: right;">${data.pseudonym} (Individual)</th>
          <th style="text-align: right;">${data.role} (Role Peer Norm)</th>
          <th>Assessment</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Typical Working Hours</td>
          <td class="text-mono" style="text-align: right;">${uBl.typical_start_hour || 9}:00 – ${uBl.typical_end_hour || 17}:00</td>
          <td class="text-mono text-muted" style="text-align: right;">${rBl.typical_start_hour || 8}:00 – ${rBl.typical_end_hour || 18}:00</td>
          <td class="text-muted" style="font-size: var(--text-xs);">Standard schedule</td>
        </tr>
        <tr>
          <td>Daily Download Volume (Median)</td>
          <td class="text-mono" style="text-align: right;">${formatBytes(uBl.download_median_bytes || 0)}</td>
          <td class="text-mono text-muted" style="text-align: right;">${formatBytes(rBl.download_median_bytes || 0)}</td>
          <td class="text-muted" style="font-size: var(--text-xs);">Robust MAD statistic</td>
        </tr>
        <tr>
          <td>Daily File Count (Median)</td>
          <td class="text-mono" style="text-align: right;">${Math.round(uBl.download_median_files || 0)} files</td>
          <td class="text-mono text-muted" style="text-align: right;">${Math.round(rBl.download_median_files || 0)} files</td>
          <td class="text-muted" style="font-size: var(--text-xs);">Typical egress count</td>
        </tr>
        <tr>
          <td>Habitual Jurisdictions</td>
          <td class="text-mono" style="text-align: right;">${(uBl.known_countries || []).join(", ") || "Domestic"}</td>
          <td class="text-mono text-muted" style="text-align: right;">${(rBl.known_countries || []).slice(0, 3).join(", ") || "Global"}</td>
          <td class="text-muted" style="font-size: var(--text-xs);">Geographic territory</td>
        </tr>
        <tr>
          <td>Known Corporate Hardware</td>
          <td class="text-mono" style="text-align: right;">${(uBl.known_devices || []).length} device(s)</td>
          <td class="text-mono text-muted" style="text-align: right;">1 – 2 devices</td>
          <td class="text-muted" style="font-size: var(--text-xs);">Asset registry inventory</td>
        </tr>
      </tbody>
    `;
    compCard.appendChild(table);
    container.appendChild(compCard);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load baseline: ${err.message}</p></div>`;
  }
}

function formatBytes(bytes) {
  if (typeof bytes !== "number" || bytes === 0) return "0 MB";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

