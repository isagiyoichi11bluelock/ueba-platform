/**
 * People View (replaces User Timeline)
 * Longitudinal telemetry profiling on pseudonymous identities:
 * 24-hour ribbon heat strip, daily download volume, habitual locations, privilege log.
 */

import { el, clearNode } from "../dom.js";
import { fetchJson } from "../api.js";
import { drawHourHeatStrip } from "../charts.js";

export async function renderPeople(container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-8); text-align: center;"><p class="text-muted">Loading people index...</p></div>`;

  try {
    const data = await fetchJson("/api/people");
    const people = data.people || [];

    if (people.length === 0) {
      container.innerHTML = `<div class="attention-callout"><p>No user accounts found in database.</p></div>`;
      return;
    }

    renderPeopleUI(container, people);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load people index: ${err.message}</p></div>`;
  }
}

function renderPeopleUI(container, people) {
  clearNode(container);

  // Header
  const headerBlock = el("div", { class: "page-header-block" },
    el("h1", {}, "Workforce Behavioral Profiles"),
    el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
      "Longitudinal behavioral telemetry. Identities are protected by HMAC-SHA256 pseudonymization."
    )
  );
  container.appendChild(headerBlock);

  // Selector Bar
  const selectorBar = el("div", {
    class: "editorial-card",
    style: "display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-6);",
  });

  selectorBar.appendChild(el("label", { style: "font-size: var(--text-sm); font-weight: 500;" }, "Select Account:"));

  const select = el("select", {
    style: "min-width: 320px;",
    onchange: (e) => loadPersonDetails(e.target.value, personDetailsContainer),
  });

  people.forEach((p, idx) => {
    const opt = el("option", { value: p.user_id }, `${p.pseudonym} — ${p.role} (${p.department})`);
    if (idx === 0) opt.selected = true;
    select.appendChild(opt);
  });
  selectorBar.appendChild(select);

  container.appendChild(selectorBar);

  const personDetailsContainer = el("div", { id: "person-details-container" });
  container.appendChild(personDetailsContainer);

  if (people.length > 0) {
    loadPersonDetails(people[0].user_id, personDetailsContainer);
  }
}

async function loadPersonDetails(userId, container) {
  container.innerHTML = `<div class="editorial-card" style="padding: var(--space-6); text-align: center;"><p class="text-muted">Loading profile telemetry…</p></div>`;

  try {
    const t = await fetchJson(`/api/people/${userId}`);
    clearNode(container);

    // Profile Metadata Row
    const metaCard = el("div", { class: "editorial-card" });
    const metaGrid = el("div", { style: "display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-4);" },
      el("div", {},
        el("span", { class: "text-muted", style: "font-size: var(--text-xs); display: block;" }, "Pseudonym"),
        el("strong", { class: "text-mono", style: "font-size: var(--text-base);" }, t.pseudonym)
      ),
      el("div", {},
        el("span", { class: "text-muted", style: "font-size: var(--text-xs); display: block;" }, "Role & Department"),
        el("span", {}, `${t.role} • ${t.department}`)
      ),
      el("div", {},
        el("span", { class: "text-muted", style: "font-size: var(--text-xs); display: block;" }, "Habitual Base"),
        el("span", {}, `${t.home_city}, ${t.home_country}`)
      ),
      el("div", {},
        el("span", { class: "text-muted", style: "font-size: var(--text-xs); display: block;" }, "Working Hours"),
        el("span", { class: "text-mono" }, `${t.work_start_hour}:00 – ${t.work_end_hour}:00`)
      )
    );
    metaCard.appendChild(metaGrid);
    container.appendChild(metaCard);

    // Two Column Layout
    const grid = el("div", { class: "editorial-grid-2" });

    // Left Column: 24-Hour Heat Strip + Daily Download Volume
    const leftCol = el("div");

    // 24-Hour Ribbon Heat Strip Card
    const heatCard = el("div", { class: "editorial-card" });
    heatCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Authentication Hour Ribbon"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Past 14 Days")
    ));
    const heatWrapper = el("div", { style: "overflow-x: auto; margin-top: var(--space-3);" });
    drawHourHeatStrip(heatWrapper, t.day_hour_matrix || {});
    heatCard.appendChild(heatWrapper);
    leftCol.appendChild(heatCard);

    // Download Volume History
    const dlCard = el("div", { class: "editorial-card" });
    dlCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Daily Egress Volume"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Observed Timeline")
    ));

    if (t.download_timeline && t.download_timeline.length > 0) {
      const dlTable = el("table", { class: "ledger-table" });
      dlTable.innerHTML = `
        <thead>
          <tr>
            <th>Date</th>
            <th style="text-align: right;">MB Transferred</th>
            <th style="text-align: right;">Files</th>
          </tr>
        </thead>
      `;
      const dlTbody = el("tbody");
      t.download_timeline.slice(-8).forEach((d) => {
        const row = el("tr");
        row.appendChild(el("td", { class: "text-mono text-muted" }, d.date));
        row.appendChild(el("td", { class: "text-mono", style: "text-align: right; font-weight: 500;" }, `${d.mb} MB`));
        row.appendChild(el("td", { class: "text-mono text-muted", style: "text-align: right;" }, d.file_count));
        dlTbody.appendChild(row);
      });
      dlTable.appendChild(dlTbody);
      dlCard.appendChild(dlTable);
    } else {
      dlCard.appendChild(el("p", { class: "text-muted" }, "No download activity recorded."));
    }
    leftCol.appendChild(dlCard);
    grid.appendChild(leftCol);

    // Right Column: Habitual Locations & Privilege Events
    const rightCol = el("div");

    // Locations Observed
    const locCard = el("div", { class: "editorial-card" });
    locCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Observed Jurisdictions"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, `${(t.locations || []).length} locations`)
    ));

    const locTable = el("table", { class: "ledger-table" });
    locTable.innerHTML = `
      <thead>
        <tr>
          <th>Territory</th>
          <th>First Seen</th>
          <th style="text-align: right;">Count</th>
        </tr>
      </thead>
    `;
    const locTbody = el("tbody");
    (t.locations || []).forEach((lc) => {
      const row = el("tr");
      row.appendChild(el("td", {}, `${lc.city}, ${lc.country}`));
      row.appendChild(el("td", { class: "text-mono text-muted", style: "font-size: var(--text-xs);" }, lc.first_seen.slice(0, 10)));
      row.appendChild(el("td", { class: "text-mono text-muted", style: "text-align: right;" }, lc.login_count));
      locTbody.appendChild(row);
    });
    locTable.appendChild(locTbody);
    locCard.appendChild(locTable);
    rightCol.appendChild(locCard);

    // Privilege Grants Log
    const privCard = el("div", { class: "editorial-card" });
    privCard.appendChild(el("div", { class: "editorial-card-header" },
      el("h3", {}, "Administrative Activity"),
      el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Privilege Operations")
    ));

    if (t.privilege_history && t.privilege_history.length > 0) {
      const pTable = el("table", { class: "ledger-table", style: "font-size: var(--text-xs);" });
      pTable.innerHTML = `
        <thead>
          <tr>
            <th>Time</th>
            <th>Action</th>
            <th>Result</th>
          </tr>
        </thead>
      `;
      const pTbody = el("tbody");
      t.privilege_history.slice(0, 6).forEach((p) => {
        const row = el("tr");
        row.appendChild(el("td", { class: "text-mono text-muted" }, p.timestamp.slice(11, 16)));
        row.appendChild(el("td", { class: "text-mono" }, p.action));
        row.appendChild(el("td", { class: "text-mono", style: p.result === "success" ? "color: var(--text-muted);" : "color: var(--accent-vermilion);" }, p.result));
        pTbody.appendChild(row);
      });
      pTable.appendChild(pTbody);
      privCard.appendChild(pTable);
    } else {
      privCard.appendChild(el("p", { class: "text-muted", style: "font-size: var(--text-xs);" }, "No elevated commands recorded."));
    }
    rightCol.appendChild(privCard);

    grid.appendChild(rightCol);
    container.appendChild(grid);
  } catch (err) {
    container.innerHTML = `<div class="attention-callout"><p>Failed to load profile details: ${err.message}</p></div>`;
  }
}

