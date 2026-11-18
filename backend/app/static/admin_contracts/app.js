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
  const previousLabel = btn?.textContent || "Скачать PDF ▾";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "PDF…";
  }

  const margin = [12, 12, 14, 12];
  const wrap = document.createElement("div");
  wrap.setAttribute("aria-hidden", "true");
  // Keep in viewport (opacity 0): off-screen -12000px often yields a blank white PDF in html2canvas.
  wrap.style.cssText =
    "position:fixed;left:0;top:0;width:190mm;padding:0;margin:0;background:#fff;color:#000;opacity:0;pointer-events:none;z-index:-1;";
  wrap.innerHTML = `
    <style>
      .sheet, .sheet * { color: #000 !important; box-sizing: border-box; }
      .sheet h1, .sheet h2, .sheet-title, .sheet-h { color: #000 !important; }
      .sheet-kv th, .sheet-kv td, .sheet-table th, .sheet-table td {
        background: #fff !important; color: #000 !important; border: 1px solid #000 !important;
      }
      .sheet-annex {
        break-before: page; page-break-before: always; margin-top: 8mm;
      }
      .sheet {
        width: 186mm; margin: 0 0 8mm; padding: 0; border: 0; box-shadow: none;
        background: #fff; color: #000; min-height: 0 !important;
      }
      .sheet-break { break-before: page; page-break-before: always; }
      .sheet-invoice-logo { width: 110px; height: auto; }
      .sheet-invoice-head { width: 100%; border: 0 !important; }
      .sheet-invoice-head td { border: 0 !important; }
    </style>
    ${renderSheets(docs)}
  `;
  document.body.appendChild(wrap);

  try {
    await loadScriptOnce("/static/admin_contracts/vendor/html2pdf.bundle.min.js?v=20261117-1");
    if (typeof window.html2pdf !== "function") {
      throw new Error("PDF-модуль не готов");
    }
    await waitForImages(wrap);
    // Force layout so canvas has real heights.
    void wrap.offsetHeight;

    const filename = pdfName(kind);
    // Do not use pagebreak mode "avoid-all" — it often yields a blank white PDF.
    const pdf = await window
      .html2pdf()
      .set({
        margin,
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
          windowWidth: Math.max(wrap.scrollWidth, 720),
        },
        jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
        pagebreak: {
          mode: ["css", "legacy"],
          before: [".sheet-annex", ".sheet-break"],
        },
      })
      .from(wrap)
      .toPdf()
      .get("pdf");

    const total = pdf.internal.getNumberOfPages();
    if (!total) throw new Error("PDF получился пустым");
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
      await downloadPdfDocs(btn.dataset.kind || "pack");
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
