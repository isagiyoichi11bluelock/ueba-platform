/**
 * Main application router and shell controller for Casebook.
 */

import { initSession, getSession, setRole } from "./api.js";
import { renderToday } from "./views/today.js";
import { renderInbox } from "./views/inbox.js";
import { renderCase } from "./views/case.js";
import { renderPeople } from "./views/people.js";
import { renderNormal } from "./views/normal.js";
import { renderRehearsal } from "./views/rehearsal.js";
import { renderLedger } from "./views/ledger.js";
import { renderSafeguards } from "./views/safeguards.js";
import { renderEvidence } from "./views/evidence.js";
import { renderStyleguide } from "./views/styleguide.js";

// Global Routes
const routes = {
  "/": renderToday,
  "/today": renderToday,
  "/inbox": renderInbox,
  "/people": renderPeople,
  "/normal": renderNormal,
  "/rehearsal": renderRehearsal,
  "/ledger": renderLedger,
  "/safeguards": renderSafeguards,
  "/evidence": renderEvidence,
  "/styleguide": renderStyleguide,
};

async function init() {
  await initSession();
  setupShell();
  setupTheme();
  setupRouter();
}

function setupShell() {
  const session = getSession();

  // Role selector
  const roleSelect = document.getElementById("header-role-select");
  if (roleSelect) {
    roleSelect.value = session.role;
    roleSelect.addEventListener("change", async (e) => {
      await setRole(e.target.value);
      route();
    });
  }

  // Theme toggle button
  const themeBtn = document.getElementById("theme-toggle-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => toggleTheme());
  }

  // Keyboard shortcut modal close
  const modalClose = document.getElementById("shortcut-modal-close");
  const modalOverlay = document.getElementById("shortcut-modal");
  if (modalClose && modalOverlay) {
    modalClose.addEventListener("click", () => modalOverlay.classList.remove("open"));
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) modalOverlay.classList.remove("open");
    });
  }
}

function setupTheme() {
  try {
    const savedTheme = localStorage.getItem("casebook-theme");
    if (savedTheme) {
      document.documentElement.setAttribute("data-theme", savedTheme);
      updateThemeButtonLabel(savedTheme);
    }
  } catch (_) {}
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  let next = "dark";
  if (current === "dark") next = "light";
  else if (!current && window.matchMedia("(prefers-color-scheme: dark)").matches) next = "light";

  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem("casebook-theme", next);
  } catch (_) {}
  updateThemeButtonLabel(next);
}

function updateThemeButtonLabel(theme) {
  const btn = document.getElementById("theme-toggle-btn");
  if (btn) {
    btn.textContent = theme === "dark" ? "Light theme" : "Dark theme";
  }
}

function setupRouter() {
  window.addEventListener("hashchange", () => route());
  window.addEventListener("popstate", () => route());

  // Intercept local link clicks
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (a && a.href && a.origin === window.location.origin && !a.getAttribute("download")) {
      const url = new URL(a.href);
      if (!url.pathname.startsWith("/api") && !url.pathname.startsWith("/static")) {
        e.preventDefault();
        history.pushState(null, "", a.href);
        route();
      }
    }
  });

  route();
}

function route() {
  const container = document.getElementById("app-main-content");
  if (!container) return;

  // Determine path from hash or pathname
  let path = window.location.hash.slice(1);
  if (!path || path === "") {
    path = window.location.pathname;
  }
  if (!path.startsWith("/")) path = "/" + path;

  // Update active nav link
  document.querySelectorAll(".nav-link").forEach((link) => {
    const target = link.getAttribute("href");
    if (target === path || (target === "/today" && path === "/")) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // Dynamic Case Route: /case/{alertId}
  if (path.startsWith("/case/")) {
    const alertId = path.split("/")[2];
    renderCase(container, alertId);
    return;
  }

  const handler = routes[path] || renderToday;
  handler(container);
  window.scrollTo(0, 0);
}

// Global start
document.addEventListener("DOMContentLoaded", init);

