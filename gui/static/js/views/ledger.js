/**
 * Ledger View (replaces Audit Log)
 * Chronological, dense, monospaced audit ledger with visible hash-chain link marks,
 * "Check the chain" verification action, simulated tamper demonstration, and CSV export.
 */

import { el, clearNode } from "../dom.js";
import { fetchJson, getSession } from "../api.js";

export async function renderLedger(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading cryptographic ledger...</p></div>`;

  try {
    const data = await fetchJson("/api/ledger?limit=60");
    renderLedgerUI(container, data);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load ledger: ${err.message}</p></div>`;
  }
}

function renderLedgerUI(container, ledgerData) {
  clearNode(container);
  const session = getSession();

  // Header
  const headerBlock = el("div", { class: "page-header-block" },
    el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: var(--space-3);" },
      el("div", {},
        el("h1", {}, "Cryptographic Audit Ledger"),
        el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
          "Immutable SHA-256 hash chain recording pipeline runs, analyst feedback, and identity re-identifications."
        )
      ),
      el("div", { style: "display: flex; gap: var(--space-2);" },
        el("button", {
          class: "btn btn-primary btn-sm",
          onclick: () => checkHashChain(container),
        }, "Check the Chain"),
        el("a", {
          href: "/api/ledger/export",
          class: "btn btn-sm",
          download: "audit_ledger.csv",
        }, "Export CSV"),
        !session.permissions.is_auditor_only
          ? el("button", {
              class: "btn btn-sm",
              style: "color: var(--accent-vermilion);",
              onclick: () => runSimulateTamper(container),
            }, "Simulate Tamper")
          : null
      )
    )
  );
  container.appendChild(headerBlock);

  // Status banner container
  const statusContainer = el("div", { id: "ledger-status-container" });
  container.appendChild(statusContainer);

  // Ledger Table Card
  const tableCard = el("div", { class: "editorial-card", style: "padding: 0; overflow-x: auto;" });
  const table = el("table", { class: "ledger-table text-mono", style: "font-size: var(--text-xs);" });

  table.innerHTML = `
    <thead>
      <tr>
        <th style="width: 50px;">Seq</th>
        <th style="width: 140px;">Timestamp (UTC)</th>
        <th style="width: 100px;">Actor</th>
        <th style="width: 160px;">Action</th>
        <th>Event Details</th>
        <th style="width: 110px;">Link</th>
        <th style="width: 120px;">Entry Hash</th>
      </tr>
    </thead>
  `;

  const tbody = el("tbody");
  const entries = ledgerData.entries || [];

  entries.forEach((e, idx) => {
    const row = el("tr");

    // Sequence
    row.appendChild(el("td", { style: "font-weight: 500;" }, `#${e.sequence_number}`));

    // Timestamp
    row.appendChild(el("td", { class: "text-muted" }, e.timestamp.slice(0, 19).replace("T", " ")));

    // Actor
    row.appendChild(el("td", {}, e.actor));

    // Action
    row.appendChild(el("td", { style: "font-weight: 500;" }, e.action));

    // Details summary
    const detailsStr = JSON.stringify(e.details);
    row.appendChild(el("td", {
      class: "text-muted",
      style: "max-width: 320px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;",
      title: detailsStr,
    }, detailsStr));

    // Visual Chain Link indicator
    const linkIcon = el("span", {
      style: "color: var(--accent-teal); font-weight: 600;",
      title: `Previous Hash: ${e.prev_hash_full}`,
    }, "⛓ " + e.prev_hash_short);
    row.appendChild(el("td", {}, linkIcon));

    // Entry Hash
    row.appendChild(el("td", {
      title: `Full Hash: ${e.entry_hash_full}`,
      style: "color: var(--text-main); font-weight: 500;",
    }, e.entry_hash_short));

    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  tableCard.appendChild(table);
  container.appendChild(tableCard);
}

async function checkHashChain(container) {
  const statusEl = document.getElementById("ledger-status-container");
  if (!statusEl) return;

  statusEl.innerHTML = `<div class="editorial-card" style="padding: var(--space-4);"><p class="text-muted">Calculating SHA-256 signatures across the full audit table…</p></div>`;

  try {
    const res = await fetchJson("/api/ledger/verify", { method: "POST" });
    if (res.valid) {
      statusEl.innerHTML = `
        <div class="context-callout" style="margin-bottom: var(--space-6);">
          <strong style="display: block; font-size: var(--text-sm);">100% Audit Chain Valid</strong>
          <p style="margin-top: 4px;">Checked all ${res.entries_checked} sequential records. Every cryptographic link verified successfully. No tampering detected.</p>
        </div>
      `;
    } else {
      statusEl.innerHTML = `
        <div class="attention-callout" style="margin-bottom: var(--space-6);">
          <strong style="display: block; font-size: var(--text-sm); color: var(--accent-vermilion);">Tampering Detected in Hash Chain</strong>
          <p style="margin-top: 4px;">Integrity signature failed at Record ID ${res.first_broken_entry}. Checked ${res.entries_checked} records before finding the broken link.</p>
        </div>
      `;
    }
  } catch (err) {
    statusEl.innerHTML = `<div class="attention-callout"><p>Verification error: ${err.message}</p></div>`;
  }
}

async function runSimulateTamper(container) {
  if (!confirm("This will simulate an attacker modifying a row in the audit database. Proceed?")) return;

  try {
    const res = await fetchJson("/api/ledger/tamper", {
      method: "POST",
      body: JSON.stringify({}),
    });
    alert(`SIMULATION APPLIED:\n${res.message}\n\nNow click 'Check the Chain' to see the cryptographic proof of tampering.`);
    renderLedger(container);
  } catch (err) {
    alert(`Tamper simulation error: ${err.message}`);
  }
}

