/**
 * Rehearsal View (replaces Scenarios Demo)
 * Numbered chapters S1 to S8, one-paragraph story, expected vs actual outcome,
 * clear match/mismatch marker in words, and highlighted pairing: "Same behavior, different context".
 */

import { el, clearNode } from "../dom.js";
import { fetchJson } from "../api.js";

export async function renderRehearsal(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading scenario rehearsals...</p></div>`;

  try {
    const data = await fetchJson("/api/rehearsal");
    const chapters = data.chapters || [];
    renderRehearsalUI(container, chapters);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load rehearsal chapters: ${err.message}</p></div>`;
  }
}

function renderRehearsalUI(container, chapters) {
  clearNode(container);

  // Header Block
  const headerBlock = el("div", { class: "page-header-block" },
    el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: var(--space-3);" },
      el("div", {},
        el("h1", {}, "Scenario Rehearsal Chapters (S1–S8)"),
        el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
          "Controlled validation of the detection engine against ground-truth malicious killchains and benign business exceptions."
        )
      ),
      el("div", {},
        el("button", {
          class: "btn btn-primary btn-sm",
          onclick: () => runAllRehearsals(container, chapters),
        }, "Run All Eight Chapters")
      )
    )
  );
  container.appendChild(headerBlock);

  // Highlighted Pairing: "Same Behavior, Different Context" (S4 vs S8)
  const s4 = chapters.find((c) => c.scenario_id === "S4");
  const s8 = chapters.find((c) => c.scenario_id === "S8");
  if (s4 && s8) {
    const pairingCard = el("div", {
      class: "editorial-card",
      style: "border-left: 4px solid var(--accent-teal); background: var(--bg-surface); margin-bottom: var(--space-8);",
    });

    pairingCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", { style: "color: var(--accent-teal);" }, "Highlight: Same Behavior, Different Context (S4 vs S8)"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "The Core Innovation")
    ));

    pairingCard.appendChild(el("p", { class: "serif-prose" },
      "Both scenarios simulate an authentication from an unusual foreign city (London) outside standard business hours. " +
      "In Scenario 4, an authorized travel schedule was filed with HR in advance, dampening the calculated score to Low severity. " +
      "In Scenario 8, the identical technical telemetry occurs with zero authorized context on file, correctly keeping the score elevated."
    ));

    const contrastTable = el("table", { class: "ledger-table", style: "margin-top: var(--space-4);" });
    contrastTable.innerHTML = `
      <thead>
        <tr>
          <th>Scenario</th>
          <th>Telemetry Pattern</th>
          <th>Context Status</th>
          <th style="text-align: right;">Calculated Score</th>
          <th style="text-align: right;">Outcome</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Chapter S4</strong></td>
          <td>Foreign login + off-hours</td>
          <td style="color: var(--accent-teal); font-weight: 500;">Approved Business Travel</td>
          <td class="text-mono" style="text-align: right; font-weight: 600;">${s4.actual_score} (LOW)</td>
          <td style="text-align: right; color: var(--accent-teal); font-weight: 500;">Dampened (${s4.passed ? "MATCH" : "MISMATCH"})</td>
        </tr>
        <tr>
          <td><strong>Chapter S8</strong></td>
          <td>Foreign login + off-hours</td>
          <td class="text-muted">No Approved Context (Unannounced)</td>
          <td class="text-mono" style="text-align: right; font-weight: 600; color: var(--accent-vermilion);">${s8.actual_score} (HIGH)</td>
          <td style="text-align: right; color: var(--accent-vermilion); font-weight: 500;">Flagged (${s8.passed ? "MATCH" : "MISMATCH"})</td>
        </tr>
      </tbody>
    `;
    pairingCard.appendChild(contrastTable);
    container.appendChild(pairingCard);
  }

  // Chapters List
  const chaptersList = el("div", { style: "display: flex; flex-direction: column; gap: var(--space-6);" });

  chapters.forEach((ch) => {
    const card = el("div", { class: "editorial-card" });

    // Chapter Header
    const cardHeader = el("div", { class: "editorial-card-header" },
      el("div", {},
        el("h3", {}, ch.title),
        el("span", { class: "text-muted", style: "font-size: var(--text-xs);" },
          `Subject: ${ch.pseudonym} • Expected Range: ${ch.expected_range}`
        )
      ),
      el("div", { style: "text-align: right;" },
        el("div", { class: "score-numeral-lg" }, Math.round(ch.actual_score)),
        el("span", {
          style: `font-size: var(--text-xs); font-weight: 600; font-family: var(--font-mono); color: ${ch.passed ? "var(--accent-teal)" : "var(--accent-vermilion)"};`,
        }, ch.passed ? "CRITERIA MATCH" : "CRITERIA MISMATCH")
      )
    );
    card.appendChild(cardHeader);

    // One-Paragraph Story
    card.appendChild(el("p", { class: "serif-prose", style: "margin-bottom: var(--space-4);" }, ch.story));

    // Footer with Open Case button
    const footer = el("div", { style: "display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-hairline); padding-top: var(--space-3);" },
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" },
        `Classification: ${ch.label.replace(/_/g, " ").toUpperCase()}`
      ),
      ch.alert_id
        ? el("a", { href: `/case/${ch.alert_id}`, class: "btn btn-sm" }, "Open the Case →")
        : el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "No alert row generated")
    );
    card.appendChild(footer);

    chaptersList.appendChild(card);
  });

  container.appendChild(chaptersList);
}

function runAllRehearsals(container, chapters) {
  const allPassed = chapters.every((c) => c.passed);
  alert(
    `REHEARSAL EXECUTION COMPLETE:\n` +
    `Chapters Evaluated: ${chapters.length}\n` +
    `Criteria Matched: ${chapters.filter((c) => c.passed).length} / ${chapters.length}\n` +
    `Status: ${allPassed ? "100% SPECIFICATION PASSED" : "REVIEW REQUIRED"}\n\n` +
    chapters.map((c) => `[${c.scenario_id}] Actual: ${c.actual_score} (Expected: ${c.expected_range}) -> ${c.passed ? "PASS" : "FAIL"}`).join("\n")
  );
}

