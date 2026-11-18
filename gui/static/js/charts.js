/**
 * Custom SVG chart generators for the Casebook interface.
 * Implements clean, restrained editorial visualizations using native SVG/D3.
 */

import { el } from "./dom.js";

/**
 * Weekly strip chart: alerts per day as quiet ticks.
 */
export function drawWeeklyStrip(container, days) {
  if (!days || days.length === 0) {
    container.appendChild(el("p", { class: "text-muted" }, "No daily activity recorded."));
    return;
  }

  const svgWidth = 600;
  const svgHeight = 90;
  const margin = { top: 15, right: 20, bottom: 25, left: 20 };
  const width = svgWidth - margin.left - margin.right;
  const height = svgHeight - margin.top - margin.bottom;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "90");
  svg.setAttribute("aria-label", "Weekly alert frequency strip chart");
  svg.style.overflow = "visible";

  // Base baseline axis line
  const baseline = document.createElementNS("http://www.w3.org/2000/svg", "line");
  baseline.setAttribute("x1", margin.left);
  baseline.setAttribute("y1", margin.top + height);
  baseline.setAttribute("x2", margin.left + width);
  baseline.setAttribute("y2", margin.top + height);
  baseline.setAttribute("stroke", "var(--border-strong)");
  baseline.setAttribute("stroke-width", "1");
  svg.appendChild(baseline);

  const step = width / (days.length - 1 || 1);
  const maxTotal = Math.max(...days.map((d) => d.total), 1);

  days.forEach((d, idx) => {
    const x = margin.left + idx * step;
    const tickHeight = Math.max(4, (d.total / maxTotal) * height);
    const y = margin.top + height - tickHeight;

    // Tick line
    const tick = document.createElementNS("http://www.w3.org/2000/svg", "line");
    tick.setAttribute("x1", x);
    tick.setAttribute("y1", margin.top + height);
    tick.setAttribute("x2", x);
    tick.setAttribute("y2", y);
    tick.setAttribute("stroke", d.high_or_critical > 0 ? "var(--accent-vermilion)" : "var(--text-muted)");
    tick.setAttribute("stroke-width", "3");
    tick.setAttribute("stroke-linecap", "square");

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${d.date}: ${d.total} cases (${d.high_or_critical} high/critical)`;
    tick.appendChild(title);
    svg.appendChild(tick);

    // Date label (every 2-3 days)
    if (idx % 2 === 0 || idx === days.length - 1) {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", x);
      text.setAttribute("y", margin.top + height + 16);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-family", "var(--font-mono)");
      text.setAttribute("font-size", "10");
      text.setAttribute("fill", "var(--text-muted)");
      text.textContent = d.date.slice(5); // MM-DD
      svg.appendChild(text);
    }
  });

  container.appendChild(svg);
}

/**
 * 24-Hour Timeline Rail for the Case View.
 * Shows working window shading, tick marks, and handwritten-style margin annotations.
 */
export function drawTimelineRail(container, events, usualStart = 9, usualEnd = 17, onSelectEvent = null) {
  const svgWidth = 860;
  const svgHeight = 110;
  const margin = { top: 30, right: 30, bottom: 30, left: 30 };
  const width = svgWidth - margin.left - margin.right;
  const height = svgHeight - margin.top - margin.bottom;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "110");
  svg.setAttribute("aria-label", "24-hour event timeline rail");

  const xPos = (hourFloat) => margin.left + (hourFloat / 24) * width;

  // Shaded band for usual working hours
  const bandX1 = xPos(usualStart);
  const bandX2 = xPos(usualEnd);
  const band = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  band.setAttribute("x", bandX1);
  band.setAttribute("y", margin.top);
  band.setAttribute("width", Math.max(0, bandX2 - bandX1));
  band.setAttribute("height", height);
  band.setAttribute("fill", "var(--bg-subtle)");
  band.setAttribute("opacity", "0.8");
  svg.appendChild(band);

  // Usual schedule label
  const bandLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
  bandLabel.setAttribute("x", (bandX1 + bandX2) / 2);
  bandLabel.setAttribute("y", margin.top - 8);
  bandLabel.setAttribute("text-anchor", "middle");
  bandLabel.setAttribute("font-family", "var(--font-sans)");
  bandLabel.setAttribute("font-size", "11");
  bandLabel.setAttribute("fill", "var(--text-muted)");
  bandLabel.textContent = `Typical hours (${usualStart}:00 – ${usualEnd}:00)`;
  svg.appendChild(bandLabel);

  // Horizontal axis rail
  const rail = document.createElementNS("http://www.w3.org/2000/svg", "line");
  rail.setAttribute("x1", margin.left);
  rail.setAttribute("y1", margin.top + height / 2);
  rail.setAttribute("x2", margin.left + width);
  rail.setAttribute("y2", margin.top + height / 2);
  rail.setAttribute("stroke", "var(--border-strong)");
  rail.setAttribute("stroke-width", "1");
  svg.appendChild(rail);

  // Hour markers (00:00, 06:00, 12:00, 18:00, 24:00)
  [0, 6, 12, 18, 24].forEach((h) => {
    const x = xPos(h);
    const tick = document.createElementNS("http://www.w3.org/2000/svg", "line");
    tick.setAttribute("x1", x);
    tick.setAttribute("y1", margin.top + height / 2 - 4);
    tick.setAttribute("x2", x);
    tick.setAttribute("y2", margin.top + height / 2 + 4);
    tick.setAttribute("stroke", "var(--border-strong)");
    tick.setAttribute("stroke-width", "1");
    svg.appendChild(tick);

    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", x);
    txt.setAttribute("y", margin.top + height + 16);
    txt.setAttribute("text-anchor", "middle");
    txt.setAttribute("font-family", "var(--font-mono)");
    txt.setAttribute("font-size", "10");
    txt.setAttribute("fill", "var(--text-muted)");
    txt.textContent = `${h.toString().padStart(2, "0")}:00`;
    svg.appendChild(txt);
  });

  // Plot event ticks
  events.forEach((ev) => {
    let hour = 12;
    try {
      const dt = new Date(ev.timestamp);
      hour = dt.getUTCHours() + dt.getUTCMinutes() / 60;
    } catch (_) {}

    const x = xPos(hour);
    const isEvidence = ev.is_evidence;

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.style.cursor = "pointer";

    const tick = document.createElementNS("http://www.w3.org/2000/svg", "line");
    tick.setAttribute("x1", x);
    tick.setAttribute("y1", margin.top + height / 2 - (isEvidence ? 16 : 8));
    tick.setAttribute("x2", x);
    tick.setAttribute("y2", margin.top + height / 2 + (isEvidence ? 16 : 8));
    tick.setAttribute("stroke", isEvidence ? "var(--accent-vermilion)" : "var(--text-muted)");
    tick.setAttribute("stroke-width", isEvidence ? "3" : "1.5");
    g.appendChild(tick);

    if (isEvidence) {
      // Circle node on top
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", margin.top + height / 2 - 16);
      dot.setAttribute("r", "4");
      dot.setAttribute("fill", "var(--accent-vermilion)");
      g.appendChild(dot);
    }

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `[${ev.type.toUpperCase()}] ${ev.timestamp.slice(11, 16)} UTC: ${ev.description}`;
    g.appendChild(title);

    if (onSelectEvent) {
      g.addEventListener("click", () => onSelectEvent(ev));
    }

    svg.appendChild(g);
  });

  container.appendChild(svg);
}

/**
 * Score Composition Stacked Bar.
 */
export function drawScoreCompositionBar(container, indicators, chainBonuses, contextApplied, finalScore) {
  const barWrapper = el("div", { style: "margin: var(--space-4) 0;" });

  const totalPoints = indicators.reduce((acc, ind) => acc + (ind.severity_points || 0), 0);
  const bonusPoints = chainBonuses.reduce((acc, b) => acc + (b.points || 0), 0);

  const barTrack = el("div", {
    style: "height: 12px; width: 100%; background: var(--bg-subtle); display: flex; border-radius: 2px; overflow: hidden; border: 1px solid var(--border-hairline);",
  });

  // Segments for indicators
  indicators.forEach((ind) => {
    const pts = ind.severity_points || 0;
    if (pts <= 0) return;
    const pct = Math.min(100, (pts / 100) * 100);
    const seg = el("div", {
      style: `height: 100%; width: ${pct}%; background: ${ind.context_dampened ? "var(--accent-teal)" : "var(--accent-vermilion)"}; opacity: 0.85; border-right: 1px solid var(--bg-surface);`,
      title: `${ind.name}: ${pts.toFixed(1)} pts`,
    });
    barTrack.appendChild(seg);
  });

  barWrapper.appendChild(barTrack);

  const legend = el(
    "div",
    { style: "display: flex; justify-content: space-between; font-size: var(--text-xs); color: var(--text-muted); font-family: var(--font-mono); margin-top: 6px;" },
    el("span", {}, `0 pts`),
    el("span", {}, `Final Score: ${Math.round(finalScore)} / 100`),
    el("span", {}, `100 pts`)
  );
  barWrapper.appendChild(legend);

  container.appendChild(barWrapper);
}

/**
 * 24-Hour Ribbon Heat Strip for People view.
 */
export function drawHourHeatStrip(container, dayHourMatrix) {
  const dates = Object.keys(dayHourMatrix).sort().slice(-14);
  if (dates.length === 0) {
    container.appendChild(el("p", { class: "text-muted" }, "No longitudinal login activity recorded."));
    return;
  }

  const table = el("table", {
    style: "border-collapse: collapse; width: 100%; font-family: var(--font-mono); font-size: 11px;",
  });

  // Header row (Hours 0 to 23)
  const thead = el("thead");
  const hRow = el("tr");
  hRow.appendChild(el("th", { style: "padding: 4px; text-align: left; color: var(--text-muted); width: 80px;" }, "Date"));
  for (let h = 0; h < 24; h += 2) {
    hRow.appendChild(el("th", { colspan: "2", style: "padding: 2px; text-align: center; color: var(--text-muted);" }, `${h}`));
  }
  thead.appendChild(hRow);
  table.appendChild(thead);

  const tbody = el("tbody");
  dates.forEach((d) => {
    const row = el("tr");
    row.appendChild(el("td", { style: "padding: 3px 6px; color: var(--text-muted); white-space: nowrap;" }, d.slice(5)));

    const hours = dayHourMatrix[d] || Array(24).fill(0);
    for (let h = 0; h < 24; h++) {
      const count = hours[h] || 0;
      let bg = "var(--bg-subtle)";
      if (count > 0) {
        const opacity = Math.min(1, 0.2 + count * 0.25);
        bg = `rgba(194, 65, 12, ${opacity})`;
      }
      const cell = el("td", {
        style: `width: 14px; height: 16px; background: ${bg}; border: 1px solid var(--bg-page);`,
        title: `${d} ${h}:00 - ${count} event(s)`,
      });
      row.appendChild(cell);
    }
    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  container.appendChild(table);
}

