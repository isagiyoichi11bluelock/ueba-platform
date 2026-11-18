/**
 * Safeguards View (replaces Privacy and Limitations)
 * Typeset long-form editorial reading page (Source Serif 4, 65-character line length, pull quotes)
 * rendering privacy guarantees, limitations, and live protection status panel.
 */

import { el, clearNode } from "../dom.js";
import { fetchJson } from "../api.js";

export async function renderSafeguards(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading safeguards declaration...</p></div>`;

  try {
    const data = await fetchJson("/api/safeguards");
    renderSafeguardsUI(container, data);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load safeguards: ${err.message}</p></div>`;
  }
}

function renderSafeguardsUI(container, data) {
  clearNode(container);

  // Header
  const headerBlock = el("div", { class: "page-header-block" },
    el("h1", {}, "Workforce Safeguards & Operating Limits"),
    el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
      "Architectural boundaries, data minimization enforcement, and honest engineering limitations."
    )
  );
  container.appendChild(headerBlock);

  // Live Technical Safeguards Status Panel
  const panelCard = el("div", { class: "editorial-card", style: "border-left: 4px solid var(--accent-teal); margin-bottom: var(--space-8);" });
  panelCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", { style: "color: var(--accent-teal);" }, "What This System Is Currently Doing to Protect People"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Enforced in Code")
  ));

  const list = el("div", { style: "display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-4);" });
  (data.live_safeguards || []).forEach((sg) => {
    const item = el("div", { style: "border: 1px solid var(--border-hairline); padding: var(--space-3); border-radius: 2px;" },
      el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;" },
        el("strong", { style: "font-size: var(--text-sm);" }, sg.name),
        el("span", { class: "text-mono", style: "color: var(--accent-teal); font-size: 11px; font-weight: 600;" }, `[${sg.status}]`)
      ),
      el("p", { class: "text-muted", style: "font-size: var(--text-xs); line-height: 1.45;" }, sg.detail)
    );
    list.appendChild(item);
  });
  panelCard.appendChild(list);
  container.appendChild(panelCard);

  // Typeset Long-form Reading Section (Serif, 65ch line length)
  const readingCard = el("div", { class: "editorial-card", style: "padding: var(--space-8);" });

  // Privacy Pillar
  readingCard.appendChild(el("h2", { style: "margin-bottom: var(--space-3);" }, "Data Minimization & Employee Dignity"));
  readingCard.appendChild(el("p", { class: "serif-prose", style: "margin-bottom: var(--space-4);" },
    "Security programs that monitor workforce behavior risk degenerating into invasive surveillance systems. " +
    "Our platform enforces data minimization at the ingestion layer: no cleartext employee names, email addresses, " +
    "or unmasked IP addresses are ever written to the analytics database. Analysts triage alerts solely against cryptographic pseudonyms."
  ));

  // Pull Quote
  const pullQuote = el("blockquote", {
    style: "border-left: 3px solid var(--border-strong); padding: var(--space-3) var(--space-5); margin: var(--space-6) 0; font-family: var(--font-serif); font-size: var(--text-lg); font-style: italic; color: var(--text-main); line-height: 1.45;",
  }, "“An anomaly is an indicator requiring review, not a conclusion of guilt. A fair system presumes good intent until corroborated by defensible evidence.”");
  readingCard.appendChild(pullQuote);

  // Limitations Pillar
  readingCard.appendChild(el("h2", { style: "margin: var(--space-8) 0 var(--space-3);" }, "Transparent Technical Limitations"));
  readingCard.appendChild(el("p", { class: "serif-prose", style: "margin-bottom: var(--space-4);" },
    "1. Baseline Poisoning: If an adversary acts gradually over more than 60 days, behavioral drift may normalize their egress volume. Machine learning without role-peer bounds is susceptible to slow-rolling attacks."
  ));
  readingCard.appendChild(el("p", { class: "serif-prose", style: "margin-bottom: var(--space-4);" },
    "2. Cold-Start Uncertainty: Workforce accounts with fewer than 14 days of tenure exhibit high variance. Blending peer baselines dampens speculative alarms, but early tenure alerts always carry lower confidence."
  ));
  readingCard.appendChild(el("p", { class: "serif-prose" },
    "3. Context Dependency: Context dampening relies on enterprise integration with HR travel rosters and maintenance on-call calendars. If a legitimate trip is unannounced in corporate systems, the engine correctly flags it for analyst verification."
  ));

  container.appendChild(readingCard);
}

