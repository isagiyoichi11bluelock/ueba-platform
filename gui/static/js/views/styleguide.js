/**
 * Living Styleguide View (/styleguide)
 * Demonstrates typographic scale, color tokens, severity marks without colored pills,
 * hairline borders, and interactive components.
 */

import { el, clearNode } from "../dom.js";

export function renderStyleguide(container) {
  clearNode(container);

  // Header
  const headerBlock = el("div", { class: "page-header-block" },
    el("h1", {}, "Casebook Design System & Styleguide"),
    el("p", { class: "text-muted", style: "font-size: var(--text-sm);" },
      "Living reference for typography, paper palette tokens, marks, and component primitives."
    )
  );
  container.appendChild(headerBlock);

  // 1. Color Palette Tokens
  const colorCard = el("div", { class: "editorial-card", style: "margin-bottom: var(--space-8);" });
  colorCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "1. Editorial Palette"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Restrained Warm Paper & Ink")
  ));

  const colorGrid = el("div", { style: "display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-4);" },
    createSwatch("Paper Background", "#F6F2EA", "var(--bg-page)", "Main background canvas"),
    createSwatch("Surface Ink", "#FFFFFF", "var(--bg-surface)", "Card & table surfaces"),
    createSwatch("Text Ink", "#1E1B16", "var(--text-main)", "Primary reading ink"),
    createSwatch("Muted Ink", "#6B645A", "var(--text-muted)", "Secondary captions & metadata"),
    createSwatch("Hairline Rule", "#D9D2C3", "var(--border-hairline)", "Delicate structural rules"),
    createSwatch("Vermilion Accent", "#C2410C", "var(--accent-vermilion)", "Attention / High urgency"),
    createSwatch("Deep Teal Accent", "#1F5F5B", "var(--accent-teal)", "Context applied / Benign explained")
  );
  colorCard.appendChild(colorGrid);
  container.appendChild(colorCard);

  // 2. Typography Hierarchy
  const typeCard = el("div", { class: "editorial-card", style: "margin-bottom: var(--space-8);" });
  typeCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "2. Typography Scale"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Source Serif 4 • IBM Plex Sans • IBM Plex Mono")
  ));

  const typeList = el("div", { style: "display: flex; flex-direction: column; gap: var(--space-4);" },
    el("div", {},
      el("h1", {}, "Headline 1 — Investigative Casebook Narrative"),
      el("span", { class: "text-mono text-muted", style: "font-size: 11px;" }, "Source Serif 4 • 36px / 600 weight")
    ),
    el("div", {},
      el("h2", {}, "Headline 2 — Data Minimization & Employee Dignity"),
      el("span", { class: "text-mono text-muted", style: "font-size: 11px;" }, "Source Serif 4 • 30px / 600 weight")
    ),
    el("div", {},
      el("h3", {}, "Headline 3 — Behavioral Baselines & Peer Norms"),
      el("span", { class: "text-mono text-muted", style: "font-size: 11px;" }, "Source Serif 4 • 24px / 600 weight")
    ),
    el("div", {},
      el("p", { class: "serif-prose" },
        "Body Prose: On 14 Nov, U-3fa9c2 signed in from an unobserved jurisdiction at 03:12 local time. " +
        "Within thirty minutes they transferred 1.4 GB against a typical 45 MB baseline."
      ),
      el("span", { class: "text-mono text-muted", style: "font-size: 11px;" }, "Source Serif 4 • 17px / 1.65 line-height / 68ch max-width")
    ),
    el("div", {},
      el("p", { class: "text-mono" }, "Monospace: EVENT-ID-LGN-7FFC94C0 • 192.168.1.0/24 • SHA256: 4a2b9f1c…"),
      el("span", { class: "text-mono text-muted", style: "font-size: 11px;" }, "IBM Plex Mono • Tabular numbers")
    )
  );
  typeCard.appendChild(typeList);
  container.appendChild(typeCard);

  // 3. Severity Marks (NOT COLORED PILLS)
  const marksCard = el("div", { class: "editorial-card", style: "margin-bottom: var(--space-8);" });
  marksCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "3. Severity Marks (No Colored Pills)"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Typography + Distinct Geometric Shapes")
  ));

  const marksGrid = el("div", { style: "display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--space-4);" },
    createMarkDemo("Critical (80–100)", "critical", "96", "Filled square + double vermilion stroke"),
    createMarkDemo("High (60–79)", "high", "74", "Solid vermilion square fill"),
    createMarkDemo("Medium (35–59)", "medium", "48", "Diagonal half-fill square mark"),
    createMarkDemo("Low (0–34)", "low", "18", "Open hairline square mark")
  );
  marksCard.appendChild(marksGrid);
  container.appendChild(marksCard);

  // 4. Component Primitives
  const compCard = el("div", { class: "editorial-card" });
  compCard.appendChild(el("div", { class: "editorial-card-header" },
    el("h3", {}, "4. Component Primitives"),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, "Callouts, Buttons, and Rules")
  ));

  const cList = el("div", { style: "display: flex; flex-direction: column; gap: var(--space-4);" },
    el("div", { class: "context-callout" },
      el("strong", {}, "Context Callout (Deep Teal)"),
      el("p", {}, "Approved business travel on file. Score reduced by 70% without silently suppressing the record.")
    ),
    el("div", { class: "attention-callout" },
      el("strong", {}, "Attention Callout (Vermilion)"),
      el("p", {}, "Unannounced credential burst followed by immediate privilege escalation.")
    ),
    el("div", { style: "display: flex; gap: var(--space-3);" },
      el("button", { class: "btn btn-primary" }, "Primary Action"),
      el("button", { class: "btn" }, "Standard Button"),
      el("button", { class: "btn btn-subtle" }, "Subtle Action"),
      el("button", { class: "btn btn-sm" }, "Small Button")
    )
  );
  compCard.appendChild(cList);
  container.appendChild(compCard);
}

function createSwatch(name, hex, varRef, note) {
  return el("div", { style: "border: 1px solid var(--border-hairline); padding: var(--space-3); border-radius: 2px;" },
    el("div", { style: `height: 48px; background: ${varRef}; border: 1px solid var(--border-hairline); border-radius: 2px; margin-bottom: 8px;` }),
    el("strong", { style: "display: block; font-size: var(--text-sm);" }, name),
    el("span", { class: "text-mono text-muted", style: "font-size: 11px; display: block;" }, hex),
    el("span", { class: "text-dim", style: "font-size: 11px; display: block; margin-top: 4px;" }, note)
  );
}

function createMarkDemo(label, band, score, desc) {
  return el("div", { style: "border: 1px solid var(--border-hairline); padding: var(--space-4); border-radius: 2px;" },
    el("div", { style: "display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;" },
      el("span", { class: `severity-mark severity-${band}` },
        el("span", { class: "mark-symbol" }),
        el("span", {}, band.toUpperCase())
      ),
      el("span", { class: "text-mono", style: "font-size: var(--text-2xl); font-weight: 600;" }, score)
    ),
    el("strong", { style: "font-size: var(--text-sm); display: block;" }, label),
    el("span", { class: "text-muted", style: "font-size: var(--text-xs);" }, desc)
  );
}

