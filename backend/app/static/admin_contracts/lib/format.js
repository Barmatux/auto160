const MONTHS = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

export function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseIsoDate(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return { y, m, d };
}

export function formatDateShort(iso) {
  const p = parseIsoDate(iso);
  if (!p) return "«__» ________ 20__ г.";
  return `${String(p.d).padStart(2, "0")}.${String(p.m).padStart(2, "0")}.${p.y}`;
}

export function formatDateLong(iso) {
  const p = parseIsoDate(iso);
  if (!p) return "«__» ________ 20__ г.";
  return `«${String(p.d).padStart(2, "0")}» ${MONTHS[p.m - 1]} ${p.y} г.`;
}

/** Invoice template style: «27 января 2026г.» */
export function formatDateInvoice(iso) {
  const p = parseIsoDate(iso);
  if (!p) return "__ ________ 20__г.";
  return `${p.d} ${MONTHS[p.m - 1]} ${p.y}г.`;
}

export function suggestContractNumber(iso, prefix = "Б") {
  const p = parseIsoDate(iso) || parseIsoDate(todayIso());
  return `${prefix}${String(p.d).padStart(2, "0")}${String(p.m).padStart(2, "0")}${String(p.y).slice(2)}`;
}

export function suggestInvoiceNumber(iso) {
  const p = parseIsoDate(iso) || parseIsoDate(todayIso());
  return `01-${String(p.d).padStart(2, "0")}${String(p.m).padStart(2, "0")}${String(p.y).slice(2)}`;
}

export function initialsFromFullName(fullName) {
  const parts = String(fullName || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "";
  if (parts.length === 1) return parts[0];
  return `${parts[0]} ${parts
    .slice(1)
    .map((p) => `${p[0]}.`)
    .join("")}`;
}

export function dash(value, fallback = "________________") {
  const v = String(value || "").trim();
  return v || fallback;
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-BY", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function clientLabel(data) {
  if (!data) return "Без клиента";
  if (data.clientType === "legal") return String(data.clientCompany || "").trim() || "Без названия";
  return String(data.clientName || "").trim() || "Без ФИО";
}
