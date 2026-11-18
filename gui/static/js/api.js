/**
 * API client with session management, role handling, and CSRF token injection.
 */

let sessionData = {
  role: "analyst",
  csrf_token: "",
  permissions: {
    can_submit_feedback: true,
    can_reidentify: false,
    is_auditor_only: false,
  },
};

export async function initSession() {
  try {
    const res = await fetch("/api/session");
    if (res.ok) {
      sessionData = await res.json();
    }
  } catch (err) {
    console.error("Session load error:", err);
  }
  return sessionData;
}

export function getSession() {
  return sessionData;
}

export async function setRole(newRole) {
  const res = await fetch("/api/session/role", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": sessionData.csrf_token,
    },
    body: JSON.stringify({ role: newRole }),
  });
  if (res.ok) {
    sessionData.role = newRole;
    sessionData.permissions.can_reidentify = newRole === "senior_analyst";
    sessionData.permissions.can_submit_feedback = newRole !== "auditor";
    sessionData.permissions.is_auditor_only = newRole === "auditor";
  }
  return res.ok;
}

export async function fetchJson(url, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.headers || {}),
  };

  if (options.method && options.method.toUpperCase() !== "GET") {
    headers["X-CSRF-Token"] = sessionData.csrf_token;
    if (!headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
  }

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorDetail = `Request failed (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) errorDetail = errJson.detail;
    } catch (_) {}
    throw new Error(errorDetail);
  }

  return res.json();
}

