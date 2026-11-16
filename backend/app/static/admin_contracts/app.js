import { applyPackageDefaults, createDefaultData, SAMPLE_CLIENT } from "./lib/defaults.js";
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
    p: "Заполните поля слева. Справа — договор, счёт и акт собираются из тех же данных.",
  },
  invoice: {
    h: "Счёт на оплату услуг",
    p: "Счёт за подбор, не за автомобиль. Форма как у ООО «Сканди Моторс»: шапка, таблица, сумма прописью.",
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
    return { ...createDefaultData(), ...JSON.parse(raw) };
  } catch {
    return createDefaultData();
  }
}

function saveLocal() {
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

  document.querySelectorAll(".rail nav button").forEach((btn) => {
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
  data = { ...createDefaultData(), ...(row.payload || {}) };
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
  const name = target.name;
  if (!name) return;
  const value = target.type === "checkbox" ? target.checked : target.value;
  if (name === "packageType") {
    data = applyPackageDefaults({ ...data, packageType: value });
    formNeedsPaint = true;
  } else {
    data = { ...data, [name]: value };
    if (name === "clientType") formNeedsPaint = true;
  }
  scheduleSave();
  paint();
}

document.getElementById("form-pane").addEventListener("change", (e) => {
  applyField(e.target);
});

document.querySelectorAll(".rail nav button").forEach((btn) => {
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

document.body.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  try {
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
      const previousTitle = document.title;
      document.title = " ";
      const restoreTitle = () => {
        document.title = previousTitle;
        window.removeEventListener("afterprint", restoreTitle);
      };
      window.addEventListener("afterprint", restoreTitle);
      window.print();
      setTimeout(restoreTitle, 1000);
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
