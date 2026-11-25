/** Desk portal: sold-cars archive (admin only). Vanilla JS, no build step. */

const API = "/api/v1/admin/sold-cars";
const root = document.getElementById("sold-app");
const deskRoot = root?.dataset.deskRoot || "";

const listPane = document.getElementById("sold-list-pane");
const detailPane = document.getElementById("sold-detail-pane");
const partnersPane = document.getElementById("sold-partners-pane");
const rowsEl = document.getElementById("sold-rows");
const emptyEl = document.getElementById("sold-empty");
const statsEl = document.getElementById("sold-stats");
const searchEl = document.getElementById("sold-search");
const reviewEl = document.getElementById("sold-only-review");

let cars = [];

function cookie(name) {
  const part = document.cookie.split("; ").find((r) => r.startsWith(`${name}=`));
  return part ? decodeURIComponent(part.slice(name.length + 1)) : null;
}

async function refreshToken() {
  const refresh = cookie("refresh_token");
  if (!refresh) return false;
  const res = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  if (!data.access_token) return false;
  document.cookie = `access_token=${data.access_token}; path=/`;
  if (data.refresh_token) document.cookie = `refresh_token=${data.refresh_token}; path=/`;
  return true;
}

async function api(path = "", { method = "GET", body, retried = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = cookie("access_token");
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    credentials: "same-origin",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if ((res.status === 401 || res.status === 403) && !retried && (await refreshToken())) {
    return api(path, { method, body, retried: true });
  }
  if (res.status === 401 || res.status === 403) {
    window.location.href = `${deskRoot}?next=${encodeURIComponent(`${deskRoot}/sold`)}`;
    throw new Error("Нет доступа");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : "Ошибка запроса");
  }
  return data;
}

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

const fmt = (n) =>
  n === null || n === undefined || n === ""
    ? "—"
    : Number(n).toLocaleString("ru-RU", { maximumFractionDigits: 2 });

function sumsText(sums) {
  const parts = Object.entries(sums || {}).map(([cur, v]) => `${fmt(v)} ${cur}`);
  return parts.length ? parts.join(" · ") : "—";
}

function badge(car) {
  if (car.needs_review) return h("span", { class: "sold-badge warn" }, car.locked ? "правится" : "проверить");
  return h("span", { class: "sold-badge ok" }, "проверено");
}

function renderList() {
  const q = searchEl.value.trim().toLowerCase();
  const onlyReview = reviewEl.checked;
  const shown = cars.filter((c) => {
    if (onlyReview && !c.needs_review) return false;
    if (!q) return true;
    return `${c.title} ${c.sheet || ""}`.toLowerCase().includes(q);
  });
  rowsEl.replaceChildren(
    ...shown.map((c) =>
      h(
        "tr",
        { class: "sold-row", onclick: () => openCar(c.id) },
        h("td", {}, h("strong", {}, c.title)),
        h("td", { class: "muted" }, c.sheet || ""),
        h("td", {}, `${c.expenses_count} шт.`, h("div", { class: "muted small" }, sumsText(c.sums))),
        h("td", {}, fmt(c.sold_price)),
        h("td", {}, fmt(c.profit)),
        h("td", {}, badge(c)),
      ),
    ),
  );
  emptyEl.hidden = cars.length > 0;
  const review = cars.filter((c) => c.needs_review).length;
  statsEl.textContent = cars.length
    ? `Всего: ${cars.length} · проверено: ${cars.length - review} · требует проверки: ${review}`
    : "";
}

function showList() {
  detailPane.hidden = true;
  partnersPane.hidden = true;
  listPane.hidden = false;
}

async function loadList() {
  cars = await api("");
  renderList();
}

function numInput(value) {
  return h("input", { type: "number", step: "0.01", value: value ?? "" });
}

function toNum(el) {
  const v = el.value.trim();
  return v === "" ? null : Number(v.replace(",", "."));
}

function rawGridTable(grid) {
  if (!grid?.length) return h("p", { class: "muted" }, "Нет сохранённого фрагмента листа.");
  const width = Math.max(...grid.map((r) => r.cells.length));
  return h(
    "div",
    { class: "sold-raw-wrap" },
    h(
      "table",
      { class: "sold-raw" },
      grid.map((row) =>
        h(
          "tr",
          {},
          h("th", {}, row.r),
          Array.from({ length: width }, (_, i) => {
            const v = row.cells[i];
            return h("td", {}, v === null || v === undefined ? "" : v);
          }),
        ),
      ),
    ),
  );
}

async function openCar(id) {
  const car = await api(`/${id}`);
  listPane.hidden = true;
  partnersPane.hidden = true;
  detailPane.hidden = false;

  const title = h("input", { value: car.title });
  const soldDate = h("input", { type: "date", value: car.sold_date || "" });
  const sold = numInput(car.sold_price);
  const cost = numInput(car.cost_price);
  const commission = numInput(car.commission);
  const profit = numInput(car.profit);
  const fx = numInput(car.fx_rate);
  const notes = h("textarea", { rows: "3" }, car.notes || "");

  const expRows = h("tbody");
  const addExpenseRow = (e = { item: "", amount: "", currency: "BYN", payer: "", note: "" }) => {
    const item = h("input", { value: e.item });
    const amount = h("input", { type: "number", step: "0.01", value: e.amount });
    const currency = h(
      "select",
      {},
      ["BYN", "USD", "EUR"].map((c) => h("option", { value: c, selected: c === e.currency }, c)),
    );
    const payer = h("input", { value: e.payer || "", class: "sold-payer" });
    const note = h("input", { value: e.note || "" });
    const tr = h(
      "tr",
      {},
      h("td", {}, item),
      h("td", {}, amount),
      h("td", {}, currency),
      h("td", {}, payer),
      h("td", {}, note),
      h("td", {}, h("button", { type: "button", class: "sold-x", title: "Удалить строку", onclick: () => tr.remove() }, "×")),
    );
    tr._get = () => ({
      item: item.value.trim(),
      amount: Number(String(amount.value).replace(",", ".")),
      currency: currency.value,
      payer: payer.value.trim() || null,
      note: note.value.trim() || null,
    });
    expRows.append(tr);
  };
  car.expenses.forEach(addExpenseRow);

  const msg = h("span", { class: "sold-msg" });

  async function save(extra = {}) {
    msg.textContent = "Сохранение…";
    const expenses = [...expRows.querySelectorAll("tr")]
      .map((tr) => tr._get())
      .filter((e) => e.item && Number.isFinite(e.amount));
    const body = {
      title: title.value.trim() || car.title,
      sold_date: soldDate.value || null,
      sold_price: toNum(sold),
      cost_price: toNum(cost),
      commission: toNum(commission),
      profit: toNum(profit),
      fx_rate: toNum(fx),
      notes: notes.value.trim() || null,
      expenses,
      clear_fields: [
        soldDate.value ? null : "sold_date",
        toNum(sold) === null ? "sold_price" : null,
        toNum(cost) === null ? "cost_price" : null,
        toNum(commission) === null ? "commission" : null,
        toNum(profit) === null ? "profit" : null,
        toNum(fx) === null ? "fx_rate" : null,
        notes.value.trim() ? null : "notes",
      ].filter(Boolean),
      ...extra,
    };
    try {
      await api(`/${id}`, { method: "PATCH", body });
      msg.textContent = "Сохранено";
      return true;
    } catch (err) {
      msg.textContent = err.message;
      return false;
    }
  }

  const field = (label, input) => h("label", { class: "sold-field" }, h("span", {}, label), input);

  detailPane.replaceChildren(
    h(
      "div",
      { class: "sold-detail-head" },
      h("button", { type: "button", class: "sold-btn", onclick: async () => { await loadList(); showList(); } }, "← К списку"),
      h("h2", {}, car.title),
      badge(car),
    ),
    car.flags.length
      ? h("ul", { class: "sold-flags" }, car.flags.map((f) => h("li", {}, f)))
      : null,
    h(
      "div",
      { class: "sold-cols" },
      h(
        "div",
        { class: "sold-form" },
        h("h3", {}, "Сделка"),
        field("Название авто", title),
        field("Дата продажи", soldDate),
        field("Продано", sold),
        field("Себестоимость", cost),
        field("Комиссия Scandi Motors", commission),
        field("Прибыль", profit),
        field("Курс (из листа)", fx),
        field("Заметки", notes),
        car.figures.length
          ? h(
              "div",
              { class: "sold-figs" },
              h("h4", {}, "Что нашёл импорт в Excel"),
              car.figures.map((f) => h("div", { class: "small" }, `${f.label} [${f.cell}]: ${f.values.map(fmt).join(" / ")}`)),
            )
          : null,
        h("div", { class: "muted small" }, `Лист: ${car.sheet || "—"} · сумма расходов: ${sumsText(car.sums)}`),
      ),
      h(
        "div",
        { class: "sold-raw-col" },
        h("h3", {}, "Исходный фрагмент Excel"),
        rawGridTable(car.raw_grid),
      ),
    ),
    h("h3", {}, "Расходы"),
    h(
      "div",
      { class: "sold-table-wrap" },
      h(
        "table",
        { class: "sold-table sold-exp" },
        h("thead", {}, h("tr", {}, ["Статья", "Сумма", "Валюта", "Кто платил", "Примечание", ""].map((t) => h("th", {}, t)))),
        expRows,
      ),
    ),
    h(
      "div",
      { class: "sold-actions" },
      h("button", { type: "button", class: "sold-btn", onclick: () => addExpenseRow() }, "+ строка расходов"),
      h("button", { type: "button", class: "sold-btn primary", onclick: async () => { if (await save()) openCar(id); } }, "Сохранить"),
      h(
        "button",
        {
          type: "button",
          class: "sold-btn primary",
          onclick: async () => {
            if (await save({ needs_review: false })) openCar(id);
          },
        },
        "Сохранить и отметить «проверено»",
      ),
      h(
        "button",
        {
          type: "button",
          class: "sold-btn danger",
          onclick: async () => {
            if (!window.confirm("Удалить это авто из базы? Excel не изменится.")) return;
            await api(`/${id}`, { method: "DELETE" });
            await loadList();
            showList();
          },
        },
        "Удалить",
      ),
      msg,
    ),
  );
  window.scrollTo(0, 0);
}

async function openPartners() {
  const partners = await api("/partners");
  listPane.hidden = true;
  detailPane.hidden = true;
  partnersPane.hidden = false;
  const msg = h("span", { class: "sold-msg" });
  partnersPane.replaceChildren(
    h(
      "div",
      { class: "sold-detail-head" },
      h("button", { type: "button", class: "sold-btn", onclick: showList }, "← К списку"),
      h("h2", {}, "Партнёры: буквы из Excel"),
    ),
    h("p", { class: "muted" }, "Впишите, кто стоит за каждой буквой в колонке «Кто платил». Сохраняется при выходе из поля."),
    h(
      "table",
      { class: "sold-table" },
      h("thead", {}, h("tr", {}, ["Код", "Имя", "Строк расходов"].map((t) => h("th", {}, t)))),
      h(
        "tbody",
        {},
        partners.map((p) => {
          const input = h("input", {
            value: p.name || "",
            placeholder: "Имя / роль",
            onchange: async () => {
              try {
                await api(`/partners/${p.id}`, { method: "PATCH", body: { name: input.value } });
                msg.textContent = `Сохранено: ${p.code}`;
              } catch (err) {
                msg.textContent = err.message;
              }
            },
          });
          return h("tr", {}, h("td", {}, h("strong", {}, p.code)), h("td", {}, input), h("td", {}, p.expenses_count));
        }),
      ),
    ),
    msg,
  );
}

searchEl.addEventListener("input", renderList);
reviewEl.addEventListener("change", renderList);
document.getElementById("sold-partners-btn").addEventListener("click", openPartners);

loadList().catch((err) => {
  statsEl.textContent = err.message;
});
