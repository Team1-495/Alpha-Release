// Thin wrapper around the UNITE backend. Paths are relative and proxied to the
// FastAPI server in development (see vite.config.js).

let token = null;

export function setToken(t) {
  token = t;
}

function authHeaders() {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(username, password) {
  const res = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Sign-in failed. Check the username and password.");
  const data = await res.json();
  setToken(data.token);
  return data; // { token, role }
}

export async function getNewcomers() {
  const res = await fetch("/v1/newcomers");
  if (!res.ok) throw new Error("Could not load newcomers.");
  return res.json();
}

export async function runMatch(topK = 3) {
  const res = await fetch("/v1/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ newcomers: [], sponsors: [], top_k: topK }),
  });
  if (!res.ok) throw new Error("Matching run failed.");
  return res.json();
}

export async function approve(newcomerId, sponsorId, override = false) {
  const res = await fetch(`/v1/matches/${newcomerId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ sponsor_id: sponsorId, override }),
  });
  if (res.status === 401) throw new Error("Sign in as a coordinator to approve matches.");
  if (!res.ok) throw new Error("Could not record the decision.");
  return res.json();
}

export async function getMatches() {
  const res = await fetch("/v1/matches");
  if (!res.ok) throw new Error("Could not load recorded matches.");
  return res.json();
}
