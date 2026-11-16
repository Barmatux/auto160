import { FINDINGS, FINDINGS_BY, KEEP_LIST } from "./lib/recommendations.js";
import { escapeHtml } from "./render.js";
import { formatDateTime } from "./lib/format.js";
import { SCHEMA_SQL } from "./lib/api.js";
import { normalizeContractData } from "./lib/defaults.js";

const LEVELS = { critical: "Критично", important: "Важно", advice: "Имеет смысл" };

function vehicleAssignmentFields(data) {
  const normalized = normalizeContractData(data);
  const rows = normalized.vehicles || [];
  const blocks = rows
    .map((row, index) => {
      const remove =
        rows.length > 1
          ? `<button type="button" class="ghost vehicle-remove" data-action="vehicle-remove" data-index="${index}">Удалить</button>`
          : "";
      return `
        <div class="vehicle-row wide" data-vehicle-index="${index}">
          <div class="vehicle-row-head">
            <span>Вариант ${index + 1}</span>
            ${remove}
          </div>
          <div class="form-grid">
            <label class="field"><span class="field-label">Марка</span>
              <input data-vehicle-index="${index}" data-vehicle-field="make" type="text" value="${escapeHtml(row.make)}" placeholder="Volkswagen" />
            </label>
            <label class="field"><span class="field-label">Модель</span>
              <input data-vehicle-index="${index}" data-vehicle-field="model" type="text" value="${escapeHtml(row.model)}" placeholder="Polo" />
            </label>
            <label class="field"><span class="field-label">Год от</span>
              <input data-vehicle-index="${index}" data-vehicle-field="yearFrom" type="text" value="${escapeHtml(row.yearFrom)}" placeholder="2016" />
            </label>
            <label class="field"><span class="field-label">Год до</span>
              <input data-vehicle-index="${index}" data-vehicle-field="yearTo" type="text" value="${escapeHtml(row.yearTo)}" placeholder="2020" />
            </label>
          </div>
        </div>`;
    })
    .join("");
  return `
    ${blocks}
    <div class="wide vehicle-add-wrap">
      <button type="button" class="ghost" data-action="vehicle-add">+ Добавить марку / модель</button>
    </div>`;
}

function field(label, name, data, extra = {}) {
  const value = data[name] ?? "";
  const wide = extra.wide ? " wide" : "";
  const hint = extra.hint ? `<span class="field-hint">${escapeHtml(extra.hint)}</span>` : "";
  let control;
  if (extra.type === "select") {
    control = `<select name="${name}">${extra.options
      .map(([v, t]) => `<option value="${escapeHtml(v)}" ${String(value) === v ? "selected" : ""}>${escapeHtml(t)}</option>`)
      .join("")}</select>`;
  } else if (extra.type === "textarea") {
    control = `<textarea name="${name}" rows="${extra.rows || 3}">${escapeHtml(value)}</textarea>`;
  } else {
    control = `<input name="${name}" type="${extra.type || "text"}" value="${escapeHtml(value)}" placeholder="${escapeHtml(extra.placeholder || "")}" />`;
  }
  return `<label class="field${wide}"><span class="field-label">${escapeHtml(label)}</span>${control}${hint}</label>`;
}

function section(title, inner) {
  return `<section class="form-section"><h3>${escapeHtml(title)}</h3><div class="form-grid">${inner}</div></section>`;
}

export function renderForm(data) {
  const clientFields =
    data.clientType === "legal"
      ? [
          field("Наименование", "clientCompany", data, { wide: true, placeholder: "ООО «...»" }),
          field("УНП", "clientUnp", data),
          field("Юридический адрес", "clientAddress", data, { wide: true }),
          field("Директор (именительный)", "clientDirector", data),
          field("Директор (родительный)", "clientDirectorGenitive", data, { hint: "в лице директора …" }),
          field("Основание полномочий", "clientBasis", data),
          field("Банковские реквизиты", "clientBankDetails", data, { wide: true }),
        ]
      : [
          field("Пол (для формулировок)", "gender", data, {
            type: "select",
            options: [
              ["male", "Мужской"],
              ["female", "Женский"],
            ],
          }),
          field("ФИО полностью", "clientName", data, { wide: true, hint: "Как в паспорте", placeholder: "Иванов Иван Иванович" }),
          field("Адрес регистрации", "clientAddress", data, { wide: true }),
          field("Паспорт", "passport", data, { placeholder: "BM1234567" }),
          field("Кем выдан", "passportIssuer", data),
          field("Дата выдачи", "passportDate", data, { type: "date" }),
          field("Идентификационный номер", "personalNumber", data),
        ];

  const by = (data.packageType || "by") !== "eu";
  const assignment = by
    ? [
        vehicleAssignmentFields(data),
        field("Пробег до, тыс. км", "mileageMax", data, { placeholder: "150" }),
        field("Топливо", "fuel", data, { placeholder: "бензин" }),
        field("Объём двигателя", "engineVolume", data, { placeholder: "1.6" }),
        field("КПП", "transmission", data, { placeholder: "автомат" }),
        field("Цвет", "color", data, { placeholder: "не белый" }),
        field("Максимальная цена ТС", "vehicleBudget", data, { placeholder: "25000" }),
        field("Валюта цены ТС", "vehicleBudgetCurrency", data, {
          type: "select",
          options: ["BYN", "USD", "EUR"].map((c) => [c, c]),
        }),
        field("VIN / конкретный лот", "vehicleVin", data, { placeholder: "если уже указан" }),
        field("Где ищем", "marketplace", data, { wide: true }),
        field("Иные пожелания", "vehicleNotes", data, {
          wide: true,
          placeholder: "один владелец, без окраса, зимняя резина",
        }),
      ]
    : [
        field("Марка", "vehicleMake", data, { placeholder: "Volkswagen" }),
        field("Модель", "vehicleModel", data, { placeholder: "Golf" }),
        field("Год от", "vehicleYearFrom", data, { placeholder: "2018" }),
        field("Год до", "vehicleYearTo", data, { placeholder: "2022" }),
        field("Максимальная цена лота", "vehicleBudget", data, { placeholder: "8500" }),
        field("Валюта лота", "vehicleBudgetCurrency", data, {
          type: "select",
          options: ["EUR", "USD", "BYN", "PLN"].map((c) => [c, c]),
        }),
        field("Площадки", "marketplace", data, { wide: true }),
        field("Иные пожелания", "vehicleNotes", data, { wide: true, placeholder: "без окраса, автомат, до 150 тыс. км" }),
      ];

  const moneyFields = [
    field("Вознаграждение, BYN", "amount", data),
    field("НДС", "vatMode", data, {
      type: "select",
      options: [
        ["none", "Не исчисляется"],
        ["included20", "20 % включён в сумму"],
        ["onTop20", "20 % сверх суммы"],
      ],
    }),
    field("Срок оплаты счёта, раб. дней", "prepaidDays", data),
    field("Срок на подпись акта, раб. дней", "actReviewDays", data),
    field("Возврат при отказе, раб. дней", "refundDays", data),
  ];
  if (!by) {
    moneyFields.push(
      field("Оплата инвойса за лот, банк. дней", "invoicePayDays", data, { hint: "Критично для аукциона" }),
      field("Ответ по ставке до (Минск)", "bidReplyTime", data),
      field("Неустойка за невыкуп, %", "penaltyPercent", data),
    );
  }

  return `
    <form class="form" id="contract-form">
      ${section(
        "Пакет документов",
        [
          field("Рынок", "packageType", data, {
            type: "select",
            options: [
              ["by", "Беларусь — поиск и подбор"],
              ["eu", "ЕС — аукционы и доставка"],
            ],
          }),
          field("Номер договора", "contractNumber", data, { placeholder: by ? "Б191026" : "П100926" }),
          field("Дата договора", "contractDate", data, { type: "date" }),
          field("Город", "city", data),
        ].join(""),
      )}
      ${section(
        "Заказчик",
        [
          field("Тип", "clientType", data, {
            type: "select",
            options: [
              ["individual", "Физическое лицо"],
              ["legal", "Юридическое лицо"],
            ],
          }),
          ...clientFields,
          field("Телефон", "clientPhone", data, { placeholder: "+375 (29) 000-00-00" }),
          field("Email", "clientEmail", data),
          field("Мессенджер", "clientMessenger", data),
        ].join(""),
      )}
      ${section("Задание на подбор", assignment.join(""))}
      ${section(
        "Стоимость и сроки",
        [
          ...moneyFields,
          `<label class="check wide"><input type="checkbox" name="photoConsent" ${data.photoConsent ? "checked" : ""} /><span>Клиент согласен на публикацию фото подобранного авто (без VIN и ФИО)</span></label>`,
        ].join(""),
      )}
      ${section(
        "Счёт на оплату",
        [
          field("Номер счёта", "invoiceNumber", data, { placeholder: `01-${(data.contractDate || "").slice(8, 10) || "дд"}${(data.contractDate || "").slice(5, 7) || "мм"}гг` }),
          field("Дата счёта", "invoiceDate", data, { type: "date" }),
        ].join(""),
      )}
      ${section(
        "Акт оказанных услуг",
        [
          field("Номер акта", "actNumber", data, { hint: "Пусто = номер договора + «-А»", placeholder: `${data.contractNumber || "Б…"}-А` }),
          field("Дата акта", "actDate", data, { type: "date" }),
          field("Период услуг с", "serviceFrom", data, { type: "date" }),
          field("Период услуг по", "serviceTo", data, { type: "date" }),
          field("Формулировка в счёте и акте", "serviceDescription", data, { type: "textarea", wide: true }),
        ].join(""),
      )}
      <details class="executor-details">
        <summary>Реквизиты Исполнителя</summary>
        <div class="form-grid">
          ${field("Полное наименование", "executorName", data, { wide: true })}
          ${field("Краткое", "executorShort", data)}
          ${field("УНП", "executorUnp", data)}
          ${field("Адрес", "executorAddress", data, { wide: true })}
          ${field("Директор", "executorDirector", data)}
          ${field("Директор в родительном", "executorDirectorGenitive", data)}
          ${field("Подпись (инициалы)", "executorDirectorShort", data)}
          ${field("Телефон", "executorPhone", data)}
          ${field("Email", "executorEmail", data)}
          ${field("Расчётный счёт", "executorAccount", data)}
          ${field("Банк", "executorBank", data, { wide: true })}
        </div>
      </details>
    </form>`;
}

export function renderAnalysis() {
  const findings = FINDINGS.map(
    (item, i) => `
      <li class="finding finding-${item.level}">
        <div class="finding-head">
          <span class="finding-num">${String(i + 1).padStart(2, "0")}</span>
          <span class="pill pill-${item.level}">${LEVELS[item.level]}</span>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <dl>
          <div><dt>Как было</dt><dd>${escapeHtml(item.was)}</dd></div>
          <div><dt>Риск</dt><dd>${escapeHtml(item.risk)}</dd></div>
          <div><dt>Как в шаблоне</dt><dd>${escapeHtml(item.fix)}</dd></div>
        </dl>
      </li>`,
  ).join("");

  return `
    <div class="analysis">
      <header class="analysis-hero">
        <p class="eyebrow">Разбор образца · Корж / XL / подбор ЕС</p>
        <h2>Что в текущем договоре ломается и что мы поправили</h2>
        <p>Образец рабочий как коммерческий щит: «мы не продавцы автомобиля». Юридически он смешанный, с дырами в сроках, учёте и потребительском праве. Ниже — конкретные правки, уже заложенные в новый шаблон.</p>
      </header>
      <section class="keep">
        <h3>Что оставляем</h3>
        <ul>${KEEP_LIST.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>
      <ol class="findings">${findings}</ol>
      <header class="analysis-hero" style="margin-top:40px">
        <p class="eyebrow">Разбор интернет-образца · подбор в Беларуси</p>
        <h2>Почему шаблон «Автогуд» нельзя брать как есть</h2>
        <p>Это чужой договор 2024 года про поиск в ЕС и лизинговые аукционы, с водяным знаком autogood.by. Для подбора на рынке РБ он и по рынку не тот, и по ответственности опасный.</p>
      </header>
      <ol class="findings">
        ${FINDINGS_BY.map(
          (item, i) => `
      <li class="finding finding-${item.level}">
        <div class="finding-head">
          <span class="finding-num">${String(i + 1).padStart(2, "0")}</span>
          <span class="pill pill-${item.level}">${LEVELS[item.level]}</span>
          <h3>${escapeHtml(item.title)}</h3>
        </div>
        <dl>
          <div><dt>Как в образце</dt><dd>${escapeHtml(item.was)}</dd></div>
          <div><dt>Риск</dt><dd>${escapeHtml(item.risk)}</dd></div>
          <div><dt>Как в шаблоне РБ</dt><dd>${escapeHtml(item.fix)}</dd></div>
        </dl>
      </li>`,
        ).join("")}
      </ol>
      <aside class="disclaimer">Шаблон подготовлен как рабочий проект документов ООО «Сканди Моторс» под законодательство Республики Беларусь. Перед массовым использованием его стоит показать вашему юристу и бухгалтеру: режим НДС, учётная политика и фактическая схема расчётов с площадками могут требовать точечной подстройки. Счёт выставляется за услугу подбора, а не за сам автомобиль — иначе вы становитесь продавцом ТС.</aside>
    </div>`;
}

export function renderLogin({ error = "", mode = "signin" } = {}) {
  const isSignup = mode === "signup";
  return `
    <div class="gate-card">
      <p class="eyebrow">Scandi Motors</p>
      <h1>${isSignup ? "Создать вход" : "Вход в архив"}</h1>
      <p class="gate-lead">Один адрес для вас и коллеги. Договоры лежат в облаке и открываются с любого компьютера.</p>
      <form data-form="${isSignup ? "signup" : "signin"}" class="gate-form">
        <label class="field wide"><span class="field-label">Email</span><input name="email" type="email" autocomplete="username" required /></label>
        <label class="field wide"><span class="field-label">Пароль</span><input name="password" type="password" autocomplete="${isSignup ? "new-password" : "current-password"}" minlength="6" required /></label>
        ${error ? `<p class="gate-error">${escapeHtml(error)}</p>` : ""}
        <button type="submit" class="primary gate-submit">${isSignup ? "Создать учётную запись" : "Войти"}</button>
      </form>
      <button type="button" class="text-btn" data-action="${isSignup ? "show-signin" : "show-signup"}">
        ${isSignup ? "Уже есть вход — войти" : "Первый раз — создать учётную запись"}
      </button>
    </div>`;
}

export function renderSetup({ error = "", url = "", anonKey = "" } = {}) {
  return `
    <div class="gate-card gate-card-wide">
      <p class="eyebrow">Подключение облака · один раз</p>
      <h1>Сделать архив общим</h1>
      <ol class="setup-steps">
        <li>Откройте <a href="https://supabase.com" target="_blank" rel="noreferrer">supabase.com</a>, создайте бесплатный проект. Регион лучше взять в ЕС (Frankfurt или Ireland).</li>
        <li>Authentication → Providers → Email: выключите <b>Confirm email</b>, сохраните.</li>
        <li>SQL Editor → New query → вставьте скрипт ниже → Run.</li>
        <li>Project Settings → API: скопируйте Project URL и anon public key.</li>
      </ol>
      <label class="field wide"><span class="field-label">SQL для облака</span>
        <textarea id="schema-sql" rows="8" readonly>${escapeHtml(SCHEMA_SQL)}</textarea>
      </label>
      <button type="button" class="ghost" data-action="copy-sql">Скопировать SQL</button>
      <form data-form="setup" class="gate-form">
        <label class="field wide"><span class="field-label">Project URL</span><input name="url" value="${escapeHtml(url)}" placeholder="https://xxxxx.supabase.co" required /></label>
        <label class="field wide"><span class="field-label">anon public key</span><textarea name="anonKey" rows="3" required placeholder="eyJhbGciOi...">${escapeHtml(anonKey)}</textarea></label>
        ${error ? `<p class="gate-error">${escapeHtml(error)}</p>` : ""}
        <button type="submit" class="primary gate-submit">Подключить облако</button>
      </form>
      <button type="button" class="text-btn" data-action="skip-cloud">Пока работать без облака</button>
      <p class="gate-note">Не копируйте service_role key — только anon public. После двух учёток в Authentication выключите «Allow new users to sign up», чтобы посторонние не регистрировались.</p>
    </div>`;
}

export function renderArchive({ rows = [], query = "", error = "" } = {}) {
  const filtered = rows.filter((row) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return `${row.contract_number || ""} ${row.client_name || ""}`.toLowerCase().includes(q);
  });
  const body = filtered.length
    ? filtered
        .map(
          (row) => `
        <tr data-action="open" data-id="${escapeHtml(row.id)}">
          <td>${escapeHtml(row.contract_number || "—")}</td>
          <td>${escapeHtml(row.client_name || "Без клиента")}</td>
          <td>${escapeHtml(row.amount ? `${row.amount} BYN` : "—")}</td>
          <td>${escapeHtml(formatDateTime(row.updated_at))}</td>
          <td class="archive-actions">
            <button type="button" data-action="delete" data-id="${escapeHtml(row.id)}">Удалить</button>
          </td>
        </tr>`,
        )
        .join("")
    : `<tr><td colspan="5" class="archive-empty">${
        rows.length ? "Ничего не найдено." : "Архив пуст. Создайте первый договор — он появится и у коллеги."
      }</td></tr>`;

  return `
    <div class="archive">
      <div class="archive-bar">
        <input name="search" value="${escapeHtml(query)}" placeholder="Поиск по клиенту или номеру" data-action="search" />
        <button type="button" class="primary" data-action="new">Новый договор</button>
      </div>
      ${error ? `<p class="gate-error">${escapeHtml(error)}</p>` : ""}
      <table class="archive-table">
        <thead>
          <tr>
            <th>Номер</th>
            <th>Клиент</th>
            <th>Сумма</th>
            <th>Изменён</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}
