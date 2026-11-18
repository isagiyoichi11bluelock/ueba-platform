/**
 * Today View (replaces Overview)
 * Editorial desk opening with data-driven prose headline, weekly tick strip,
 * top cases requiring review, compact ledger table, and per-role small multiples.
 */

import { el } from "../dom.js";
import { fetchJson } from "../api.js";
import { drawWeeklyStrip } from "../charts.js";

export async function renderToday(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading today's casefile...</p></div>`;

  try {
    const data = await fetchJson("/api/today");
    container.innerHTML = "";

    // Headline prose
    const headerBlock = el("div", { class: "page-header-block" },
      el("p", { class: "editorial-headline" }, data.headline || "Telemetric baseline is active."),
      el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
        `Current ledger records ${data.total_alerts} cases across the 15-day evaluation window. `,
        el("strong", {}, `${data.open_count} open cases`),
        ` remain unreviewed, with `,
        el("span", { class: "severity-critical", style: "font-weight: 500;" }, `${data.critical_count} critical`),
        " and ",
        el("span", { class: "severity-high", style: "font-weight: 500;" }, `${data.high_count} high-priority`),
        " files."
      )
    );
    container.appendChild(headerBlock);

    // Main 2-column layout
    const grid = el("div", { class: "editorial-grid-2" });

    // Left Column: Top Cases Needing Review + Weekly Activity Strip
    const leftCol = el("div");

    // Top Cases Section
    const casesCard = el("div", { class: "editorial-card" });
    const casesHeader = el("div", { class: "editorial-card-header" },
      el("h3", {}, "Cases Needing Review"),
      el("a", { href: "/inbox", class: "btn btn-subtle btn-sm" }, "View All in Inbox →")
    );
    casesCard.appendChild(casesHeader);

    if (data.top_cases && data.top_cases.length > 0) {
      const casesTable = el("table", { class: "ledger-table" });
      casesTable.innerHTML = `
        <thead>
          <tr>
            <th>Mark</th>
            <th>Subject</th>
            <th>Role</th>
            <th>Date</th>
            <th>Score</th>
            <th>Action</th>
          </tr>
        </thead>
      `;
      const tbody = el("tbody");
      data.top_cases.forEach((c) => {
        const tr = el("tr");
        const markClass = `severity-${c.severity_band}`;

        tr.appendChild(el("td", {},
          el("span", { class: `severity-mark ${markClass}` },
            el("span", { class: "mark-symbol" }),
            el("span", {}, c.severity_band.toUpperCase())
          )
        ));
        tr.appendChild(el("td", { class: "text-mono" }, c.pseudonym));
        tr.appendChild(el("td", {}, c.role));
        tr.appendChild(el("td", { class: "text-mono text-muted" }, c.date));
        tr.appendChild(el("td", { class: "text-mono", style: "font-weight: 600;" }, Math.round(c.risk_score)));
        tr.appendChild(el("td", {},
          el("a", { href: `/case/${c.alert_id}`, class: "btn btn-sm" }, "Open File")
        ));
        tbody.appendChild(tr);
      });
      casesTable.appendChild(tbody);
      casesCard.appendChild(casesTable);
    } else {
      casesCard.appendChild(el("p", { class: "text-muted" }, "No cases currently flagged for urgent review."));
    }
    leftCol.appendChild(casesCard);

    // Weekly Strip Chart Card
    const stripCard = el("div", { class: "editorial-card" });
    stripCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Daily Case Activity"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Past 14 Days")
    ));
    const stripWrapper = el("div", { style: "padding: var(--space-2) 0;" });
    drawWeeklyStrip(stripWrapper, data.daily_strip);
    stripCard.appendChild(stripWrapper);
    leftCol.appendChild(stripCard);

    grid.appendChild(leftCol);

    // Right Column: Summary Ledger Table + Per-Role Activity
    const rightCol = el("div");

    // Compact Summary Ledger
    const ledgerCard = el("div", { class: "editorial-card" });
    ledgerCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Triage Ledger"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Status Counts")
    ));

    const ledgerTable = el("table", { class: "ledger-table" });
    ledgerTable.innerHTML = `
      <tbody>
        <tr>
          <td>Critical Attention</td>
          <td class="text-mono" style="text-align: right; font-weight: 600; color: var(--accent-vermilion);">${data.critical_count}</td>
          <td class="text-muted" style="text-align: right; font-size: var(--text-xs);">Requires same-day look</td>
        </tr>
        <tr>
          <td>High Priority</td>
          <td class="text-mono" style="text-align: right; font-weight: 600;">${data.high_count}</td>
          <td class="text-muted" style="text-align: right; font-size: var(--text-xs);">Investigation pending</td>
        </tr>
        <tr>
          <td>Moderate / Low</td>
          <td class="text-mono" style="text-align: right;">${data.medium_count + data.low_count}</td>
          <td class="text-muted" style="text-align: right; font-size: var(--text-xs);">Context-dampened</td>
        </tr>
        <tr>
          <td>Reviewed / Closed</td>
          <td class="text-mono" style="text-align: right;">${data.reviewed_count}</td>
          <td class="text-muted" style="text-align: right; font-size: var(--text-xs);">${data.total_alerts > 0 ? Math.round((data.reviewed_count / data.total_alerts) * 100) : 0}% review progress</td>
        </tr>
      </tbody>
    `;
    ledgerCard.appendChild(ledgerTable);
    rightCol.appendChild(ledgerCard);

    // Role Activity Small Multiples
    const roleCard = el("div", { class: "editorial-card" });
    roleCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Departmental Norms"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Alert Share")
    ));

    const roleTable = el("table", { class: "ledger-table" });
    roleTable.innerHTML = `
      <thead>
        <tr>
          <th>Role</th>
          <th style="text-align: right;">Cases</th>
          <th style="text-align: right;">Avg Score</th>
        </tr>
      </thead>
    `;
    const rTbody = el("tbody");
    (data.role_activity || []).forEach((r) => {
      const rRow = el("tr");
      rRow.appendChild(el("td", {}, r.role));
      rRow.appendChild(el("td", { class: "text-mono", style: "text-align: right;" }, r.total));
      rRow.appendChild(el("td", { class: "text-mono", style: "text-align: right;" }, r.avg_score));
      rTbody.appendChild(rRow);
    });
    roleTable.appendChild(rTbody);
    roleCard.appendChild(roleTable);
    rightCol.appendChild(roleCard);

    grid.appendChild(rightCol);
    container.appendChild(grid);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Unable to load Today view: ${err.message}</p></div>`;
  }
}

