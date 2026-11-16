/** Auto160 admin API client for selection-service contracts. */

const API_BASE = "/api/v1/admin/contracts";

function translateError(message, status) {
  const text = String(message || "");
  if (status === 401 || status === 403 || /unauthorized|forbidden/i.test(text)) {
    return "Нет доступа. Войдите в админку Auto160.";
  }
  if (/failed to fetch|networkerror|load failed/i.test(text)) {
    return "Нет связи с сервером Auto160.";
  }
  return text || "Не получилось выполнить запрос.";
}

async function apiFetch(path = "", { method = "GET", body } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
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
