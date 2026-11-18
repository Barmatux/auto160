import { applyPackageDefaults, createDefaultData, normalizeContractData, SAMPLE_CLIENT } from "./lib/defaults.js";
import { buildContract, isByPackage } from "./lib/contract.js";
import { buildByContract } from "./lib/contractBy.js";
import { buildAct } from "./lib/act.js";
import { buildInvoice } from "./lib/invoice.js";
import { moneyPhrase } from "./lib/money.js";
import { suggestContractNumber, todayIso } from "./lib/format.js";
import { downloadWord, renderSheet } from "./render.js";
import { renderAnalysis, renderArchive, renderForm } from "./ui.js";
import {
  createContract,
  deleteContract,
  getContract,
  getSession,
  listContracts,
  updateContract,
} from "./lib/api.js";

const STORAGE_KEY = "auto160-admin-contract-draft-v1";

const titles = {
  archive: {
    h: "Архив договоров",
    p: "Общий список для админов Auto160. Откройте договор или создайте новый.",
  },
  contract: {
    h: "Договор подбора",
    p: "Заполните поля слева — справа договор, счёт и акт собираются из тех же данных.",
  },
  invoice: {
    h: "Счёт на оплату авто",
    p: "Форма как в шаблоне Сканди Моторс: реквизиты, покупатель, легковой автомобиль / VIN, сумма прописью.",
  },
  act: {
    h: "Акт сдачи-приёмки",
    p: "Акт закрывает услугу для учёта. Он привязан к этому же договору и счёту.",
  },
  analysis: {
    h: "Разбор образцов",
    p: "Почему шаблон из интернета и XL-договор ЕС нельзя копировать как есть, и что стоит в генераторе.",
  },
};

function loadLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return createDefaultData();
    return normalizeContractData({ ...createDefaultData(), ...JSON.parse(raw) });
  } catch {
    return createDefaultData();
  }
}

function saveLocal() {
  data = normalizeContractData(data);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function currentDocument() {
  if (tab === "invoice") return buildInvoice(data);
  if (tab === "act") return buildAct(data);
  return isByPackage(data) ? buildByContract(data) : buildContract(data);
}

function wordName(kind) {
  const stamp = data.contractNumber || "draft";
  if (kind === "invoice") return `Schet_${stamp}.doc`;
  if (kind === "act") return `Akt_${stamp}.doc`;
  return `Dogovor_${stamp}.doc`;
}

let view = "boot";
let tab = "contract";
let data = loadLocal();
let recordId = null;
let records = [];
let query = "";
let formNeedsPaint = true;
let archiveError = "";
let saveState = "";
let saveTimer = 0;

function sessionUser() {
  return getSession()?.user || null;
}

function setSaveStatus(text) {
  saveState = text;
  const el = document.getElementById("save-status");
  if (el) el.textContent = text;
}

async function persistCloud() {
  if (!recordId) return;
  try {
    setSaveStatus("Сохранение…");
    await updateContract(recordId, data);
    setSaveStatus("Сохранено");
  } catch (err) {
    setSaveStatus(err.message || "Не удалось сохранить");
  }
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  saveLocal();
  setSaveStatus(recordId ? "Есть несохранённые правки" : "Черновик в браузере");
  saveTimer = window.setTimeout(() => persistCloud(), 900);
}

function paint() {
  const workspace = document.getElementById("workspace");
  const single = document.getElementById("single-pane");
  const formPane = document.getElementById("form-pane");
  const preview = document.getElementById("preview-pane");
  const user = sessionUser();

  document.getElementById("user-label").textContent = user?.email || "Админ";
  document.getElementById("amount-box").textContent = moneyPhrase(data.amount);
  document.getElementById("save-status").textContent = saveState;

  const screen = tab === "archive" ? "archive" : tab;
  const heading = titles[screen] || titles.contract;
  document.getElementById("toolbar-title").textContent =
    screen === "contract"
      ? isByPackage(data)
        ? "Договор подбора в Беларуси"
        : "Договор подбора ЕС"
      : heading.h;
  document.getElementById("toolbar-lead").textContent = (titles[screen] || titles.contract).p;
  document.getElementById("doc-actions").hidden = screen === "archive" || screen === "analysis";
  document.getElementById("btn-sample").hidden = screen === "archive" || screen === "analysis";

  document.querySelectorAll(".contracts-tabs button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  if (tab === "archive") {
    const activeSearch = document.activeElement?.dataset?.action === "search";
    const caret = activeSearch ? document.activeElement.selectionStart : null;
    workspace.hidden = true;
    single.hidden = false;
    single.innerHTML = renderArchive({ rows: records, query, error: archiveError });
    const search = single.querySelector("[data-action=search]");
    if (activeSearch && search) {
      search.focus();
      if (caret != null) search.setSelectionRange(caret, caret);
    }
    return;
  }

  if (tab === "analysis") {
    workspace.hidden = true;
    single.hidden = false;
    single.innerHTML = renderAnalysis();
    return;
  }

  view = "editor";
  workspace.hidden = false;
  single.hidden = true;
  formPane.hidden = false;
  preview.hidden = false;
  if (formNeedsPaint) {
    formPane.innerHTML = renderForm(data);
    formNeedsPaint = false;
  }
  preview.innerHTML = renderSheet(currentDocument());
}

async function loadArchive() {
  archiveError = "";
  try {
    records = await listContracts();
  } catch (err) {
    records = [];
    archiveError = err.message;
  }
}

async function openRecord(id) {
  const row = await getContract(id);
  if (!row) throw new Error("Договор не найден.");
  recordId = row.id;
  data = normalizeContractData({ ...createDefaultData(), ...(row.payload || {}) });
  formNeedsPaint = true;
  view = "editor";
  tab = "contract";
  setSaveStatus("Сохранено");
  paint();
}

async function createNew() {
  data = createDefaultData();
  formNeedsPaint = true;
  const row = await createContract(data);
  recordId = row.id;
  setSaveStatus("Сохранено");
  saveLocal();
  view = "editor";
  tab = "contract";
  paint();
}

document.getElementById("form-pane").addEventListener("input", (e) => {
  applyField(e.target);
});

function applyField(target) {
  if (target.dataset.vehicleField != null) {
    const index = Number(target.dataset.vehicleIndex || 0);
    const fieldName = target.dataset.vehicleField;
    const vehicles = [...(normalizeContractData(data).vehicles || [])];
    while (vehicles.length <= index) {
      vehicles.push({ make: "", model: "", yearFrom: "", yearTo: "" });
    }
    vehicles[index] = { ...vehicles[index], [fieldName]: target.value };
    data = normalizeContractData({ ...data, vehicles });
    scheduleSave();
    paint();
    return;
  }
  const name = target.name;
  if (!name) return;
  const value = target.type === "checkbox" ? target.checked : target.value;
  if (name === "packageType") {
    data = applyPackageDefaults({ ...data, packageType: value });
    formNeedsPaint = true;
  } else {
    data = { ...data, [name]: value };
    if (name === "clientType") formNeedsPaint = true;
    if (["vehicleMake", "vehicleModel", "vehicleYearFrom", "vehicleYearTo"].includes(name)) {
      data = normalizeContractData(data);
    }
  }
  scheduleSave();
  paint();
}

document.getElementById("form-pane").addEventListener("change", (e) => {
  applyField(e.target);
});

document.querySelectorAll(".contracts-tabs button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    tab = btn.dataset.tab;
    try {
      if (tab === "archive") {
        view = "archive";
        await loadArchive();
      } else if (tab === "analysis") {
        view = "editor";
      } else {
        view = "editor";
        formNeedsPaint = true;
      }
      paint();
    } catch (err) {
      archiveError = err.message;
      paint();
    }
  });
});

document.body.addEventListener("input", (e) => {
  if (e.target.dataset.action === "search") {
    query = e.target.value;
    paint();
  }
});

function loadScriptOnce(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "1") resolve();
      else existing.addEventListener("load", () => resolve(), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.src = src;
    script.addEventListener("load", () => {
      script.dataset.loaded = "1";
      resolve();
    }, { once: true });
    script.addEventListener("error", () => reject(new Error("Не удалось загрузить модуль PDF")), { once: true });
    document.head.appendChild(script);
  });
}

async function downloadPdfPreview() {
  const sheet = document.querySelector(".preview-pane .sheet");
  if (!sheet) return;

  const btn = document.getElementById("btn-print");
  const previousLabel = btn?.textContent || "Скачать PDF";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "PDF…";
  }

  const margin = [16, 16, 16, 16]; // mm — even margins reduce canvas slice drift

  const wrap = document.createElement("div");
  wrap.setAttribute("aria-hidden", "true");
  wrap.style.cssText =
    "position:fixed;left:-12000px;top:0;width:178mm;padding:0;margin:0;background:#fff;color:#000;pointer-events:none;";
  const clone = sheet.cloneNode(true);
  clone.style.cssText =
    "width:178mm;margin:0;padding:0;border:0;box-shadow:none;background:#fff;color:#000;min-height:0;";
  const forceInk = document.createElement("style");
  forceInk.textContent = `
    .sheet, .sheet * { color: #000 !important; }
    .sheet h1, .sheet h2, .sheet-title, .sheet-h { color: #000 !important; }
    .sheet-kv th, .sheet-kv td, .sheet-table th, .sheet-table td {
      background: #fff !important;
      color: #000 !important;
      border-color: #000 !important;
    }
    .sheet-keep, .signs, .sheet-kv, .sheet-kv tr, .sheet-table tr {
      break-inside: avoid !important;
      page-break-inside: avoid !important;
    }
    .sheet-h {
      page-break-after: avoid !important;
      break-after: avoid-page !important;
    }
    .sheet-annex {
      break-before: page !important;
      page-break-before: always !important;
    }
  `;
  wrap.appendChild(forceInk);
  wrap.appendChild(clone);
  document.body.appendChild(wrap);

  try {
    await loadScriptOnce("/static/admin_contracts/vendor/html2pdf.bundle.min.js?v=20261117-1");
    if (typeof window.html2pdf !== "function") {
      throw new Error("PDF-модуль не готов");
    }
    const kind = tab === "invoice" ? "invoice" : tab === "act" ? "act" : "contract";
    const filename = wordName(kind).replace(/\.doc$/i, ".pdf");
    // No manual page-break spacers — they created empty "holes". Keep heading+next via .sheet-keep.
    const pdf = await window
      .html2pdf()
      .set({
        margin,
        filename,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          backgroundColor: "#ffffff",
          logging: false,
          scrollX: 0,
          scrollY: 0,
        },
        jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
        pagebreak: {
          mode: ["avoid-all", "css"],
          before: [".sheet-annex"],
          avoid: [".sheet-keep", ".signs", ".sheet-kv", ".sheet-kv tr", ".sheet-table tr", ".sheet-p"],
        },
      })
      .from(clone)
      .toPdf()
      .get("pdf");
    const total = pdf.internal.getNumberOfPages();
    for (let i = 1; i <= total; i += 1) {
      pdf.setPage(i);
      pdf.setFont("times", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(0, 0, 0);
      const w = pdf.internal.pageSize.getWidth();
      const h = pdf.internal.pageSize.getHeight();
      pdf.text(String(i), w / 2, h - 8, { align: "center" });
    }
    pdf.save(filename);
  } finally {
    wrap.remove();
    if (btn) {
      btn.disabled = false;
      btn.textContent = previousLabel;
    }
  }
}

document.body.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  try {
    if (action === "vehicle-add") {
      const vehicles = [...(normalizeContractData(data).vehicles || [])];
      vehicles.push({ make: "", model: "", yearFrom: "", yearTo: "" });
      data = normalizeContractData({ ...data, vehicles });
      formNeedsPaint = true;
      scheduleSave();
      paint();
      return;
    }
    if (action === "vehicle-remove") {
      const index = Number(btn.dataset.index || 0);
      const vehicles = [...(normalizeContractData(data).vehicles || [])];
      if (vehicles.length <= 1) return;
      vehicles.splice(index, 1);
      data = normalizeContractData({ ...data, vehicles });
      formNeedsPaint = true;
      scheduleSave();
      paint();
      return;
    }
    if (action === "new") {
      await createNew();
    } else if (action === "open") {
      await openRecord(btn.dataset.id);
    } else if (action === "delete") {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm("Удалить договор из архива?")) return;
      await deleteContract(btn.dataset.id);
      if (String(recordId) === String(btn.dataset.id)) recordId = null;
      await loadArchive();
      tab = "archive";
      view = "archive";
      paint();
    } else if (action === "sample") {
      const date = data.contractDate || todayIso();
      data = {
        ...data,
        ...SAMPLE_CLIENT,
        contractNumber: data.contractNumber || suggestContractNumber(date, isByPackage(data) ? "Б" : "П"),
        contractDate: date,
        actDate: data.actDate || date,
        serviceFrom: date,
        serviceTo: data.actDate || date,
      };
      formNeedsPaint = true;
      tab = "contract";
      scheduleSave();
      paint();
    } else if (action === "print") {
      await downloadPdfPreview();
    } else if (action === "word") {
      const kind = tab === "invoice" ? "invoice" : tab === "act" ? "act" : "contract";
      downloadWord(currentDocument(), wordName(kind));
    } else if (action === "both") {
      const docs = [
        [isByPackage(data) ? buildByContract(data) : buildContract(data), wordName("contract")],
        [buildInvoice(data), wordName("invoice")],
        [buildAct(data), wordName("act")],
      ];
      docs.forEach((item, i) => setTimeout(() => downloadWord(item[0], item[1]), i * 400));
    }
  } catch (err) {
    archiveError = err.message;
    paint();
  }
});

async function boot() {
  data = loadLocal();
  view = "archive";
  tab = "archive";
  try {
    await loadArchive();
  } catch (err) {
    archiveError = err.message;
    view = "editor";
    tab = "contract";
  }
  paint();
}

boot();
