/** Auto160 admin API client for selection-service contracts. */

const API_BASE = "/api/v1/admin/contracts";

function getCookie(name) {
  const prefix = `${name}=`;
  const part = document.cookie.split("; ").find((row) => row.startsWith(prefix));
  return part ? decodeURIComponent(part.slice(prefix.length)) : null;
}

function setAuthCookies(accessToken, refreshToken) {
  document.cookie = `access_token=${accessToken}; path=/`;
  document.cookie = `refresh_token=${refreshToken}; path=/`;
}

async function refreshAccessTokenIfNeeded() {
  const refreshToken = getCookie("refresh_token");
  if (!refreshToken) return false;
  const response = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return false;
  const data = await response.json();
  if (!data.access_token || !data.refresh_token) return false;
  setAuthCookies(data.access_token, data.refresh_token);
  return true;
}

function translateError(message, status) {
  const text = String(message || "");
  if (status === 401 || status === 403 || /unauthorized|forbidden/i.test(text)) {
    return "Нет доступа. Войдите по логину на этой странице.";
  }
  if (/failed to fetch|networkerror|load failed/i.test(text)) {
    return "Нет связи с сервером.";
  }
  return text || "Не получилось выполнить запрос.";
}

async function apiFetch(path = "", { method = "GET", body, _retried = false } = {}) {
  const headers = body ? { "Content-Type": "application/json" } : {};
  const access = getCookie("access_token");
  if (access) headers.Authorization = `Bearer ${access}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "same-origin",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
  }
  if ((res.status === 401 || res.status === 403) && !_retried) {
    const refreshed = await refreshAccessTokenIfNeeded();
    if (refreshed) {
      return apiFetch(path, { method, body, _retried: true });
    }
  }
  if (!res.ok) {
    const msg =
      (typeof data?.detail === "string" && data.detail) ||
      data?.message ||
      data?.error ||
      raw;
    const err = new Error(translateError(msg, res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

export function isCloudConfigured() {
  return true;
}

export function getSession() {
  const email =
    document.getElementById("admin-contracts-root")?.dataset?.userEmail || "admin";
  return { user: { email } };
}

export function getCloudConfig() {
  return { url: "", anonKey: "" };
}

export function saveCloudConfig() {}
export function signIn() {
  return getSession();
}
export function signUp() {
  return getSession();
}
export function signOut() {}

export const SCHEMA_SQL = "";

export async function listContracts() {
  return apiFetch("");
}

export async function getContract(id) {
  return apiFetch(`/${encodeURIComponent(id)}`);
}

export async function createContract(payload) {
  return apiFetch("", { method: "POST", body: { payload } });
}

export async function updateContract(id, payload) {
  return apiFetch(`/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: { payload },
  });
}

export async function deleteContract(id) {
  await apiFetch(`/${encodeURIComponent(id)}`, { method: "DELETE" });
}
