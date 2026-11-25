import { applyPackageDefaults, createDefaultData, normalizeContractData, SAMPLE_CLIENT } from "./lib/defaults.js";
import { buildContract, isByPackage } from "./lib/contract.js";
import { buildByContract } from "./lib/contractBy.js";
import { buildAct } from "./lib/act.js";
import { buildCarInvoice, buildInvoice } from "./lib/invoice.js";
import { moneyPhrase } from "./lib/money.js";
import { suggestContractNumber, todayIso } from "./lib/format.js";
import { downloadWord, renderSheet, renderSheets } from "./render.js?v=20261118-15";
import { renderAnalysis, renderArchive, renderForm } from "./ui.js?v=20261118-15";
import {
  createContract,
  deleteContract,
  getContract,
  getSession,
  listContracts,
  updateContract,
} from "./lib/api.js";

const STORAGE_KEY = "auto160-admin-contract-draft-v1";
const DRAFT_STACK_KEY = "auto160-admin-contract-draft-stack-v1";

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

function readDraftStack() {
  try {
    const raw = localStorage.getItem(DRAFT_STACK_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function writeDraftStack(list) {
  localStorage.setItem(DRAFT_STACK_KEY, JSON.stringify(list.slice(0, 12)));
}

/** Snapshot current form before an overwrite so the user can restore it. */
function pushDraftSnapshot(reason) {
  try {
    saveLocal();
    const stack = readDraftStack();
    stack.unshift({
      at: Date.now(),
      reason: reason || "правка",
      recordId,
      data: JSON.parse(JSON.stringify(normalizeContractData(data))),
    });
    writeDraftStack(stack);
  } catch {
    /* ignore quota */
  }
  updateRestoreButton();
}

function updateRestoreButton() {
  const btn = document.getElementById("btn-restore-draft");
  if (!btn) return;
  const stack = readDraftStack();
  btn.hidden = stack.length === 0;
  if (stack.length) {
    const when = new Date(stack[0].at).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
    btn.title = `Вернуть: ${stack[0].reason || "черновик"} · ${when}`;
    btn.textContent = `Вернуть черновик (${stack.length})`;
  }
}

function restoreDraftSnapshot() {
  const stack = readDraftStack();
  if (!stack.length) return;
  const snap = stack.shift();
  writeDraftStack(stack);
  data = normalizeContractData({ ...createDefaultData(), ...(snap.data || {}) });
  recordId = snap.recordId ?? recordId;
  formNeedsPaint = true;
  tab = "contract";
  view = "editor";
  saveLocal();
  setSaveStatus("Восстановлен черновик");
  paint();
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
  updateRestoreButton();

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
    formPane.innerHTML = renderForm(data, { tab });
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
  pushDraftSnapshot("перед открытием другого договора");
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
  pushDraftSnapshot("перед новым договором");
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
    pushDraftSnapshot("перед сменой рынка (Беларусь / ЕС)");
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

async function waitForImages(root) {
  await Promise.all(
    [...root.querySelectorAll("img")].map(async (img) => {
      if (!img.getAttribute("src")) return;
      if (!img.complete || img.naturalWidth === 0) {
        await new Promise((resolve) => {
          img.addEventListener("load", resolve, { once: true });
          img.addEventListener("error", resolve, { once: true });
        });
      }
      // Same-origin → data URL so html2canvas never paints a blank logo tile.
      try {
        if (img.src && !img.src.startsWith("data:")) {
          const res = await fetch(img.src, { credentials: "same-origin" });
          if (res.ok) {
            const blob = await res.blob();
            img.src = await new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result || ""));
              reader.onerror = reject;
              reader.readAsDataURL(blob);
            });
          }
        }
      } catch {
        /* keep original src */
      }
    }),
  );
}

/** A4 content width must match jsPDF margins or html2canvas clips the left edge. */
const PDF_MARGIN_MM = [18, 18, 18, 18]; // top, left, bottom, right
const PDF_CONTENT_WIDTH_MM = 210 - PDF_MARGIN_MM[1] - PDF_MARGIN_MM[3]; // 174mm

// Scoped under #contracts-pdf-root so portal .sheet (210mm + 25mm pad + grid signs) cannot leak.
const PDF_DOC_CSS = `
  #contracts-pdf-root, #contracts-pdf-root * { box-sizing: border-box !important; color: #000 !important; }
  #contracts-pdf-root {
    font-family: "Times New Roman", Times, serif !important;
    font-size: 12pt !important;
    line-height: 1.35 !important;
    background: #fff !important;
    color: #000 !important;
  }
  #contracts-pdf-root .sheet {
    width: 100% !important;
    max-width: none !important;
    min-height: 0 !important;
    height: auto !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    background: #fff !important;
    color: #000 !important;
    position: static !important;
    font-family: "Times New Roman", Times, serif !important;
    font-size: 12pt !important;
    line-height: 1.35 !important;
  }
  #contracts-pdf-root .sheet-break,
  #contracts-pdf-root .sheet-annex,
  #contracts-pdf-root .sheet-annex-only {
    page-break-before: always !important;
    break-before: page !important;
  }
  #contracts-pdf-root .sheet-annex {
    margin-top: 0 !important;
    padding-top: 8pt !important;
    border-top: 0 !important;
  }
  #contracts-pdf-root .sheet-title {
    text-align: center !important;
    font-size: 14pt !important;
    font-weight: bold !important;
    margin: 6pt 0 4pt !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
  }
  #contracts-pdf-root .sheet-sub {
    text-align: center !important;
    font-style: italic !important;
    margin: 0 0 2pt !important;
  }
  #contracts-pdf-root .sheet-h {
    font-size: 12pt !important;
    font-weight: bold !important;
    margin: 12pt 0 4pt !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    page-break-after: avoid !important;
  }
  #contracts-pdf-root .sheet-h.center { text-align: center !important; }
  #contracts-pdf-root .sheet-keep {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
  }
  #contracts-pdf-root .sheet-p {
    margin: 0 0 6pt !important;
    text-align: justify !important;
    page-break-inside: auto !important;
    break-inside: auto !important;
  }
  #contracts-pdf-root .sheet-p.preamble { text-indent: 1.25em !important; margin-bottom: 10pt !important; }
  #contracts-pdf-root .sheet-note { font-size: 10pt !important; font-style: italic !important; margin: 6pt 0 !important; }
  #contracts-pdf-root .sheet-space { height: 8pt !important; margin: 0 !important; }
  #contracts-pdf-root .sheet-letterhead { margin: 0 0 10pt !important; line-height: 1.35 !important; }
  #contracts-pdf-root .letter-line { margin: 0 !important; padding: 0 !important; line-height: 1.35 !important; }
  #contracts-pdf-root .sheet-kicker {
    text-align: center !important;
    font-size: 9pt !important;
    letter-spacing: .08em !important;
    text-transform: uppercase !important;
    margin: 0 0 6pt !important;
  }
  #contracts-pdf-root .sheet-kv,
  #contracts-pdf-root .sheet-table {
    border-collapse: collapse !important;
    width: 100% !important;
    margin: 8pt 0 12pt !important;
    table-layout: auto !important;
  }
  #contracts-pdf-root .sheet-kv th,
  #contracts-pdf-root .sheet-kv td,
  #contracts-pdf-root .sheet-table th,
  #contracts-pdf-root .sheet-table td {
    border: 1px solid #000 !important;
    padding: 4pt 5pt !important;
    vertical-align: top !important;
    background: #fff !important;
    font-size: 10pt !important;
  }
  #contracts-pdf-root .sheet-table th { font-size: 9pt !important; text-align: center !important; }
  #contracts-pdf-root .sheet-kv,
  #contracts-pdf-root .sheet-kv tr,
  #contracts-pdf-root .sheet-table tr,
  #contracts-pdf-root .signs {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
  }
  #contracts-pdf-root .sheet-invoice-head,
  #contracts-pdf-root .sheet-invoice-head td,
  #contracts-pdf-root .sheet-meta,
  #contracts-pdf-root .sheet-meta td,
  #contracts-pdf-root .signs,
  #contracts-pdf-root .signs td {
    border: 0 !important;
    background: transparent !important;
  }
  #contracts-pdf-root .sheet-meta { margin: 10pt 0 12pt !important; width: 100% !important; }
  #contracts-pdf-root .sheet-invoice-head { margin-bottom: 12pt !important; width: 100% !important; }
  #contracts-pdf-root .sheet-invoice-logo {
    width: 90px !important;
    max-width: 90px !important;
    height: auto !important;
    display: block !important;
  }
  #contracts-pdf-root .sheet-invoice-title { text-align: center !important; font-weight: bold !important; margin: 12pt 0 8pt !important; }
  #contracts-pdf-root .sheet-invoice-buyer { white-space: pre-line !important; margin: 0 0 10pt !important; }
  #contracts-pdf-root table.signs,
  #contracts-pdf-root .signs {
    display: table !important;
    width: 100% !important;
    margin-top: 18pt !important;
    grid-template-columns: none !important;
    gap: 0 !important;
  }
  #contracts-pdf-root .sign-col {
    display: table-cell !important;
    width: 50% !important;
    vertical-align: top !important;
    padding-right: 12pt !important;
  }
  #contracts-pdf-root .sign-title { font-weight: bold !important; margin: 0 0 4pt !important; }
  #contracts-pdf-root .sign-line-text { margin: 0 !important; }
  #contracts-pdf-root .sign-gap { height: 18pt !important; margin: 0 !important; line-height: 18pt !important; }
  #contracts-pdf-root .sign-role { margin: 0 !important; font-style: italic !important; }
  #contracts-pdf-root .sign-line { margin: 4pt 0 0 !important; }
  #contracts-pdf-root .sign-line-single { margin: 22pt 0 0 !important; }
  #contracts-pdf-root .signs-single { display: block !important; margin-top: 28pt !important; }
  #contracts-pdf-root .page-break { display: none !important; }
`;

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
  if (!docs.length) {
    window.alert("Нечего сохранять в PDF.");
    return;
  }

  const btn = document.getElementById("btn-print");
  const previousLabel = btn?.textContent || "Скачать PDF ▾";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "PDF…";
  }

  // Keep the export DOM on-screen (under a white overlay). Off-screen / opacity:0 → blank PDF.
  const overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:2147483646;background:#fff;display:flex;align-items:center;justify-content:center;font:16px/1.4 -apple-system,BlinkMacSystemFont,sans-serif;color:#111;";
  overlay.textContent = "Готовим PDF…";
  document.body.appendChild(overlay);

  const wrap = document.createElement("div");
  wrap.id = "contracts-pdf-root";
  // Exact printable width (= A4 − side margins). Wider containers → left clipping + striped gaps.
  wrap.style.cssText = `position:fixed;left:0;top:0;width:${PDF_CONTENT_WIDTH_MM}mm;padding:0;margin:0;overflow:visible;z-index:2147483645;background:#fff;color:#000;`;
  // Word-safe markup (tables for signs/meta) — same as .doc export; avoids CSS grid in capture.
  let html = renderSheets(docs, { word: true });
  html = html.replace(/<br[^>]*page-break[^>]*>/gi, "");
  html = html.replace(/<p class="page-break"[^>]*>[\s\S]*?<\/p>/gi, "");
  wrap.innerHTML = `<style>${PDF_DOC_CSS}</style><div id="contracts-pdf-body">${html}</div>`;
  document.body.appendChild(wrap);

  try {
    await loadScriptOnce("/static/admin_contracts/vendor/html2pdf.bundle.min.js?v=20261117-1");
    if (typeof window.html2pdf !== "function") {
      throw new Error("PDF-модуль не готов");
    }

    const target = wrap.querySelector("#contracts-pdf-body");
    await waitForImages(target);
    if (document.fonts?.ready) {
      try {
        await document.fonts.ready;
      } catch {
        /* ignore */
      }
    }
    await new Promise((r) => window.setTimeout(r, 80));
    void target.offsetHeight;

    if (!target || target.scrollHeight < 20) {
      throw new Error("Документ для PDF пуст");
    }

    const captureWidth = Math.ceil(target.getBoundingClientRect().width || target.scrollWidth || 650);
    const filename = pdfName(kind);
    await window
      .html2pdf()
      .set({
        margin: PDF_MARGIN_MM,
        filename,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          allowTaint: true,
          backgroundColor: "#ffffff",
          logging: false,
          scrollX: 0,
          scrollY: 0,
          x: 0,
          y: 0,
          windowWidth: captureWidth,
          windowHeight: Math.ceil(target.scrollHeight) + 24,
          onclone(clonedDoc) {
            const root = clonedDoc.getElementById("contracts-pdf-root");
            if (root) {
              root.style.cssText = `position:absolute;left:0;top:0;width:${PDF_CONTENT_WIDTH_MM}mm;padding:0;margin:0;overflow:visible;opacity:1;visibility:visible;background:#fff;color:#000;transform:none;`;
            }
            const body = clonedDoc.getElementById("contracts-pdf-body");
            if (body) {
              body.style.cssText = "width:100%;margin:0;padding:0;color:#000;background:#fff;";
            }
            clonedDoc.querySelectorAll("#contracts-pdf-root .sheet").forEach((el) => {
              el.style.minHeight = "0";
              el.style.height = "auto";
              el.style.padding = "0";
              el.style.margin = "0";
              el.style.width = "100%";
              el.style.border = "0";
              el.style.boxShadow = "none";
              el.style.background = "#fff";
            });
          },
        },
        jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
        // avoid-all + css (no legacy): legacy mode was slicing canvas into striped pages with holes.
        pagebreak: {
          mode: ["avoid-all", "css"],
          before: [".sheet-break", ".sheet-annex", ".sheet-annex-only"],
          avoid: [".sheet-keep", ".signs", ".sheet-kv", ".sheet-kv tr", ".sheet-table tr"],
        },
      })
      .from(target)
      .save();
  } catch (err) {
    console.error(err);
    window.alert(err?.message || "Не удалось сохранить PDF");
    throw err;
  } finally {
    wrap.remove();
    overlay.remove();
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
      pushDraftSnapshot("перед вставкой примера");
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
    } else if (action === "restore-draft") {
      restoreDraftSnapshot();
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
      try {
        await downloadPdfDocs(btn.dataset.kind || "pack");
      } catch (err) {
        // downloadPdfDocs already alerts; keep editor state
        setSaveStatus(err?.message || "Ошибка PDF");
      }
      return;
    } else if (action === "word") {
      closeExportMenus();
      const kind = btn.dataset.kind || "pack";
      const wordBtn = document.getElementById("btn-word");
      const prev = wordBtn?.textContent || "Скачать Word ▾";
      if (wordBtn) {
        wordBtn.disabled = true;
        wordBtn.textContent = "Word…";
      }
      try {
        await downloadWord(resolveExportDocs(kind), wordName(kind));
      } finally {
        if (wordBtn) {
          wordBtn.disabled = false;
          wordBtn.textContent = prev;
        }
      }
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
  // Keep a recoverable copy of whatever was already typed before further edits.
  if (
    !readDraftStack().length &&
    (data.clientName || data.clientCompany || data.contractNumber || data.amount)
  ) {
    pushDraftSnapshot("автосохранение при открытии");
  }
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
