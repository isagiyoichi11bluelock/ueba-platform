/**
 * Inbox View (replaces Alert Queue)
 * Email-inbox style dense list with keyboard navigation (j/k, Enter, b, s, m, /, ?)
 */

import { el, clearNode } from "../dom.js";
import { fetchJson, getSession } from "../api.js";

let alertsList = [];
let selectedIndex = 0;

export async function renderInbox(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading inbox cases...</p></div>`;

  try {
    const data = await fetchJson("/api/inbox");
    alertsList = data.alerts || [];
    selectedIndex = 0;

    renderInboxUI(container);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load inbox: ${err.message}</p></div>`;
  }
}

function renderInboxUI(container) {
  clearNode(container);

  // Header & Controls
  const headerBlock = el("div", { class: "page-header-block", style: "margin-bottom: var(--space-4);" },
    el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: var(--space-3);" },
      el("div", {},
        el("h1", {}, "Case Inbox"),
        el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
          "Dense review queue. Use ",
          el("span", { class: "kbd-badge" }, "j"), " / ", el("span", { class: "kbd-badge" }, "k"),
          " to navigate, ", el("span", { class: "kbd-badge" }, "Enter"), " to open, ",
          el("span", { class: "kbd-badge" }, "?"), " for shortcuts."
        )
      ),
      el("div", { style: "display: flex; align-items: center; gap: var(--space-2);" },
        el("input", {
          id: "inbox-search-input",
          type: "search",
          placeholder: "Filter by pseudonym or role (/ to focus)…",
          style: "width: 280px;",
          oninput: (e) => filterList(container, e.target.value),
        }),
        el("button", {
          class: "btn btn-subtle btn-sm",
          onclick: () => document.getElementById("shortcut-modal")?.classList.add("open"),
        }, "Shortcuts [?]")
      )
    )
  );
  container.appendChild(headerBlock);

  // Filter Bar
  const filterBar = el("div", {
    style: "display: flex; align-items: center; gap: var(--space-4); font-size: var(--text-xs); color: var(--text-muted); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-hairline); margin-bottom: var(--space-4); flex-wrap: wrap;",
  },
    el("span", {}, "Filter:"),
    createFilterButton("All Severities", "all", container),
    createFilterButton("Critical & High", "urgent", container, true),
    createFilterButton("Open Only", "open", container),
    createFilterButton("Reviewed", "reviewed", container)
  );
  container.appendChild(filterBar);

  // Table Container
  const tableWrapper = el("div", { class: "editorial-card", style: "padding: 0; overflow-x: auto;" });
  const table = el("table", { class: "ledger-table", id: "inbox-table" });
  table.innerHTML = `
    <thead>
      <tr>
        <th style="width: 110px;">Mark</th>
        <th style="width: 60px;">Score</th>
        <th style="width: 100px;">Subject</th>
        <th style="width: 120px;">Role</th>
        <th>Top Reasons</th>
        <th style="width: 110px;">Date</th>
        <th style="width: 90px;">Status</th>
        <th style="width: 80px; text-align: right;">Action</th>
      </tr>
    </thead>
  `;

  const tbody = el("tbody", { id: "inbox-tbody" });
  table.appendChild(tbody);
  tableWrapper.appendChild(table);
  container.appendChild(tableWrapper);

  renderTableRows();
  setupKeyboardListener();
}

let activeFilter = "urgent";

function createFilterButton(label, value, container, defaultActive = false) {
  const btn = el("button", {
    class: `btn btn-subtle btn-sm ${activeFilter === value ? "active" : ""}`,
    style: activeFilter === value ? "font-weight: 600; text-decoration: underline;" : "",
    onclick: () => {
      activeFilter = value;
      renderInboxUI(container);
    },
  }, label);
  return btn;
}

function renderTableRows() {
  const tbody = document.getElementById("inbox-tbody");
  if (!tbody) return;
  clearNode(tbody);

  let filtered = alertsList;
  if (activeFilter === "urgent") {
    filtered = alertsList.filter((a) => a.severity_band === "critical" || a.severity_band === "high");
  } else if (activeFilter === "open") {
    filtered = alertsList.filter((a) => a.status === "open");
  } else if (activeFilter === "reviewed") {
    filtered = alertsList.filter((a) => a.status !== "open");
  }

  if (filtered.length === 0) {
    tbody.appendChild(el("tr", {},
      el("td", { colspan: "8", style: "padding: var(--space-8); text-align: center; color: var(--text-muted);" },
        "Nothing waiting in this view. All cases in this category are clear."
      )
    ));
    return;
  }

  filtered.forEach((a, idx) => {
    const isSelected = idx === selectedIndex;
    const markClass = `severity-${a.severity_band}`;

    const tr = el("tr", {
      class: isSelected ? "table-row-selected" : "",
      dataset: { idx: String(idx), alertId: a.alert_id },
      onclick: () => {
        selectedIndex = idx;
        renderTableRows();
      },
      ondblclick: () => {
        window.location.hash = `/case/${a.alert_id}`;
      },
    });

    // Mark
    tr.appendChild(el("td", {},
      el("span", { class: `severity-mark ${markClass}` },
        el("span", { class: "mark-symbol" }),
        el("span", {}, a.severity_band.toUpperCase())
      )
    ));

    // Score Numeral
    tr.appendChild(el("td", { class: "text-mono", style: "font-weight: 600;" }, Math.round(a.risk_score)));

    // Pseudonym
    tr.appendChild(el("td", { class: "text-mono" }, a.pseudonym));

    // Role
    tr.appendChild(el("td", { class: "text-muted" }, a.role));

    // Reasons summary
    tr.appendChild(el("td", { style: "max-width: 380px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;" },
      a.reasons_summary
    ));

    // Date
    tr.appendChild(el("td", { class: "text-mono text-muted", style: "font-size: var(--text-xs);" }, a.alert_date));

    // Status
    tr.appendChild(el("td", { class: "text-mono text-muted", style: "font-size: var(--text-xs);" }, a.status));

    // Action
    tr.appendChild(el("td", { style: "text-align: right;" },
      el("a", { href: `/case/${a.alert_id}`, class: "btn btn-sm" }, "Open")
    ));

    tbody.appendChild(tr);
  });
}

function filterList(container, searchStr) {
  const query = searchStr.toLowerCase().trim();
  const rows = document.querySelectorAll("#inbox-tbody tr");
  rows.forEach((r) => {
    const text = r.textContent?.toLowerCase() || "";
    r.style.display = text.includes(query) ? "" : "none";
  });
}

function setupKeyboardListener() {
  document.onkeydown = (e) => {
    // If typing in input, ignore j/k
    if (document.activeElement?.tagName === "INPUT" || document.activeElement?.tagName === "TEXTAREA") {
      if (e.key === "Escape") document.activeElement.blur();
      return;
    }

    if (e.key === "j") {
      selectedIndex = Math.min(alertsList.length - 1, selectedIndex + 1);
      renderTableRows();
      e.preventDefault();
    } else if (e.key === "k") {
      selectedIndex = Math.max(0, selectedIndex - 1);
      renderTableRows();
      e.preventDefault();
    } else if (e.key === "Enter") {
      const selected = alertsList[selectedIndex];
      if (selected) {
        window.location.hash = `/case/${selected.alert_id}`;
      }
    } else if (e.key === "/") {
      e.preventDefault();
      document.getElementById("inbox-search-input")?.focus();
    } else if (e.key === "?") {
      e.preventDefault();
      document.getElementById("shortcut-modal")?.classList.add("open");
    }
  };
}

