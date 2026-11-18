import { applyPackageDefaults, createDefaultData, normalizeContractData, SAMPLE_CLIENT } from "./lib/defaults.js";
import { buildContract, isByPackage } from "./lib/contract.js";
import { buildByContract } from "./lib/contractBy.js";
import { buildAct } from "./lib/act.js";
import { buildCarInvoice, buildInvoice } from "./lib/invoice.js";
import { moneyPhrase } from "./lib/money.js";
import { suggestContractNumber, todayIso } from "./lib/format.js";
import { downloadWord, renderSheet, renderSheets } from "./render.js";
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
    p: "Справа: договор, приложение, счёт и акт. PDF/Word — пакет или отдельные страницы.",
  },
  invoice: {
    h: "Счёт на оплату авто",
    p: "Отдельный документ: шапка Сканди Моторс, предмет — автомобиль / VIN. В пакете договора печатается счёт за услуги подбора.",
  },
  act: {
    h: "Акт сдачи-приёмки",
    p: "Акт закрывает услугу подбора. Привязан к договору и счёту на услуги.",
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

function buildFullContract() {
  return isByPackage(data) ? buildByContract(data) : buildContract(data);
}

function buildContractOnlyDoc() {
  const full = buildFullContract();
  return { ...full, annex1: null };
}

function buildAnnexOnlyDoc() {
  const full = buildFullContract();
  return {
    kind: "annex",
    title: "",
    subtitle: [],
    meta: { city: "", date: "" },
    preamble: "",
    blocks: [],
    annex1: full.annex1 || null,
    signatures: full.signatures,
  };
}

function currentDocument() {
  if (tab === "invoice") return buildCarInvoice(data);
  if (tab === "act") return buildAct(data);
  return buildFullContract();
}

/** Preview HTML for the active tab. Contract pack uses service invoice, not car invoice. */
function previewHtml() {
  if (tab === "invoice") return renderSheet(buildCarInvoice(data));
  if (tab === "act") return renderSheet(buildAct(data));
  return renderSheets([buildFullContract(), buildInvoice(data), buildAct(data)]);
}

function resolveExportDocs(kind) {
  if (kind === "invoice") return [buildInvoice(data)];
  if (kind === "car-invoice") return [buildCarInvoice(data)];
  if (kind === "act") return [buildAct(data)];
  if (kind === "annex") return [buildAnnexOnlyDoc()];
  if (kind === "contract") return [buildContractOnlyDoc()];
  // pack: договор + приложение + счёт на услуги + акт
  const docs = [buildContractOnlyDoc()];
  const annex = buildAnnexOnlyDoc();
  if (annex.annex1?.length) docs.push(annex);
  docs.push(buildInvoice(data), buildAct(data));
  return docs;
}

function wordName(kind) {
  const stamp = data.contractNumber || "draft";
  if (kind === "invoice") return `Schet_uslugi_${stamp}.doc`;
  if (kind === "car-invoice") return `Schet_avto_${stamp}.doc`;
  if (kind === "act") return `Akt_${stamp}.doc`;
  if (kind === "annex") return `Prilozhenie_${stamp}.doc`;
  if (kind === "pack") return `Paket_${stamp}.doc`;
  return `Dogovor_${stamp}.doc`;
}

function pdfName(kind) {
  return wordName(kind).replace(/\.doc$/i, ".pdf");
}

function closeExportMenus() {
  document.querySelectorAll(".export-menu-list").forEach((el) => {
    el.hidden = true;
  });
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
  preview.innerHTML = previewHtml();
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

async function downloadPdfDocs(kind) {
  const docs = resolveExportDocs(kind).filter(
    (doc) =>
      doc &&
      ((doc.blocks && doc.blocks.length) ||
        (doc.annex1 && doc.annex1.length) ||
        doc.preamble ||
        doc.title ||
        doc.logoSrc),
  );
  if (!docs.length) return;

  const btn = document.getElementById("btn-print");
  const previousLabel = btn?.textContent || "Скачать PDF";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "PDF…";
  }

  const margin = [16, 16, 16, 16];
  const wrap = document.createElement("div");
  wrap.setAttribute("aria-hidden", "true");
  wrap.style.cssText =
    "position:fixed;left:-12000px;top:0;width:178mm;padding:0;margin:0;background:#fff;color:#000;pointer-events:none;";
  wrap.innerHTML = `
    <style>
      .sheet, .sheet * { color: #000 !important; }
      .sheet h1, .sheet h2, .sheet-title, .sheet-h { color: #000 !important; }
      .sheet-kv th, .sheet-kv td, .sheet-table th, .sheet-table td {
        background: #fff !important; color: #000 !important; border-color: #000 !important;
      }
      .sheet-keep, .signs, .sheet-kv, .sheet-kv tr, .sheet-table tr {
        break-inside: avoid !important; page-break-inside: avoid !important;
      }
      .sheet-h { page-break-after: avoid !important; break-after: avoid-page !important; }
      .sheet-annex, .sheet-break, .sheet-annex-only {
        break-before: page !important; page-break-before: always !important;
      }
      .sheet {
        width: 178mm; margin: 0; padding: 0; border: 0; box-shadow: none;
        background: #fff; color: #000; min-height: 0;
      }
      .sheet-invoice-logo { width: 110px; height: auto; }
    </style>
    ${renderSheets(docs)}
  `;
  document.body.appendChild(wrap);

  try {
    await loadScriptOnce("/static/admin_contracts/vendor/html2pdf.bundle.min.js?v=20261117-1");
    if (typeof window.html2pdf !== "function") {
      throw new Error("PDF-модуль не готов");
    }
    // Wait for logo image so html2canvas captures it.
    await Promise.all(
      [...wrap.querySelectorAll("img")].map(
        (img) =>
          img.complete
            ? Promise.resolve()
            : new Promise((resolve) => {
                img.addEventListener("load", resolve, { once: true });
                img.addEventListener("error", resolve, { once: true });
              }),
      ),
    );
    const filename = pdfName(kind);
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
          before: [".sheet-annex", ".sheet-break", ".sheet-annex-only"],
          avoid: [".sheet-keep", ".signs", ".sheet-kv", ".sheet-kv tr", ".sheet-table tr", ".sheet-p"],
        },
      })
      .from(wrap)
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
    } else if (action === "toggle-pdf" || action === "toggle-word") {
      e.preventDefault();
      const menuName = action === "toggle-pdf" ? "pdf" : "word";
      const menu = document.querySelector(`[data-menu="${menuName}"]`);
      const wasOpen = menu && !menu.hidden;
      closeExportMenus();
      if (menu && !wasOpen) menu.hidden = false;
      return;
    } else if (action === "pdf") {
      closeExportMenus();
      await downloadPdfDocs(btn.dataset.kind || "pack");
    } else if (action === "word") {
      closeExportMenus();
      const kind = btn.dataset.kind || "pack";
      downloadWord(resolveExportDocs(kind), wordName(kind));
    }
  } catch (err) {
    archiveError = err.message;
    paint();
  }
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".export-menu")) closeExportMenus();
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
