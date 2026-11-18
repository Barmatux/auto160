import { dash, formatDateInvoice, formatDateLong, initialsFromFullName } from "./format.js";
import { computeVat, formatAmount, moneyToWords } from "./money.js";

export const INVOICE_LOGO_SRC = "/static/admin_contracts/brand/scandi-motors-invoice.png";

function buyerLines(d) {
  if (d.clientType === "legal") {
    return [
      dash(d.clientCompany, "________________"),
      d.clientUnp ? `УНП ${d.clientUnp}` : "",
      dash(d.clientAddress, ""),
      d.clientPhone ? `тел. ${d.clientPhone}` : "",
    ].filter(Boolean);
  }
  return [
    dash(d.clientName, "________________"),
    dash(d.clientAddress, ""),
    d.passport ? `паспорт ${d.passport}` : "",
    d.personalNumber ? `идентификационный номер ${d.personalNumber}` : "",
    d.clientPhone ? `тел. ${d.clientPhone}` : "",
  ].filter(Boolean);
}

function letterhead(d) {
  // Header layout from Scandi Motors invoice sample (logo + requisites only).
  return [
    dash(d.executorShort, "ООО «Сканди Моторс»"),
    "Юридический адрес:",
    dash(d.executorAddress, "г. Минск, ул. Скрыганова, дом 6, помещение 7."),
    `УНП:${dash(d.executorUnp, "193866357")}`,
    `Тел (Viber / WhatsApp / Telegram): ${dash(d.executorPhone, "+375336987799")}`,
    dash(d.executorEmail, "scandimotorsby@gmail.com"),
    "Банковские реквизиты:",
    `Р/c ${dash(d.executorAccount, "BY58 ALFA 3012 2G91 3900 1027 0000")} в BYN`,
    dash(d.executorBank, "ЗАО «АЛЬФА-БАНК». 220013 Минск, ул. Сурганова, 43-47."),
    `СВИФТ - ${dash(d.executorSwift, "ALFABY2X")}, УНП ${dash(d.executorBankUnp, "101541947")}, ОКПО ${dash(
      d.executorOkpo,
      "37526626",
    )}.`,
  ].join("\n");
}

function directorSign(d) {
  return {
    mode: "single",
    line: `___________________ Директор ${dash(
      d.executorDirectorShort,
      initialsFromFullName(d.executorDirector) || "__________",
    )}`,
  };
}

function invoiceShell({ number, dateIso, buyer, itemName, amount, vatMode }) {
  const vat = computeVat(amount, vatMode || "none");
  const vatCell = vat.rate ? formatAmount(vat.vat) : "Без НДС";
  const unitPrice = vat.rate ? formatAmount(vat.net) : formatAmount(vat.gross);
  const withVat = formatAmount(vat.gross);
  return {
    blocks: [
      {
        type: "p",
        text: `Счет № ${number} от ${formatDateInvoice(dateIso)}`,
        className: "sheet-invoice-title",
      },
      { type: "space" },
      {
        type: "p",
        text: `Покупатель:\n${buyer}`,
        className: "sheet-invoice-buyer",
      },
      {
        type: "table",
        columns: [
          "№",
          "Наименование товара, услуги",
          "Кол-во",
          "Цена, руб. коп.",
          "НДС , руб. коп.",
          "Цена с НДС, руб. коп.",
          "Всего к оплате, руб. коп.",
        ],
        rows: [["1", itemName, "1", unitPrice, vatCell, withVat, withVat]],
      },
      {
        type: "p",
        text: `Итого к оплате: ${formatAmount(vat.gross)} руб. (${moneyToWords(vat.gross)}).`,
      },
    ],
  };
}

function serviceItemName(d) {
  const description = dash(
    d.serviceDescription,
    "Информационно-консультационные услуги по подбору транспортного средства",
  );
  return [
    description,
    `по договору № ${dash(d.contractNumber)} от ${formatDateLong(d.contractDate)}`,
  ].join("\n");
}

/** Счёт на оплату услуг подбора — идёт в пакет договора / PDF / Word. */
export function buildInvoice(d) {
  const number = (d.invoiceNumber || "").trim() || `01-________`;
  const dateIso = d.invoiceDate || d.contractDate;
  const { blocks } = invoiceShell({
    number,
    dateIso,
    buyer: buyerLines(d).join(", "),
    itemName: serviceItemName(d),
    amount: d.amount || "0",
    vatMode: d.vatMode || "none",
  });
  return {
    kind: "invoice",
    logoSrc: INVOICE_LOGO_SRC,
    kicker: "",
    title: "",
    subtitle: [],
    meta: { city: "", date: "" },
    preamble: letterhead(d),
    blocks,
    signatures: directorSign(d),
  };
}

function invoiceCarLabel(d) {
  const make = String(d.invoiceCarMake || d.vehicleMake || "").trim();
  const model = String(d.invoiceCarModel || d.vehicleModel || "").trim();
  const year = String(d.invoiceCarYear || d.vehicleYearFrom || d.vehicleYearTo || "").trim();
  const car = [make, model].filter(Boolean).join(" ");
  if (car && year) return `${car} ${year} г.в.`;
  if (car) return car;
  if (year) return `${year} г.в.`;
  return "________________";
}

function carItemName(d) {
  const vin = String(d.invoiceCarVin || d.vehicleVin || "").trim();
  const lines = ["Легковой автомобиль", invoiceCarLabel(d)];
  lines.push(vin ? `VIN ${vin}` : "VIN ________________");
  return lines.join("\n");
}

function carInvoiceAmount(d) {
  const raw = String(d.invoiceAmount ?? "").trim();
  return raw || "0";
}

/** Отдельный счёт на оплату авто (вкладка) — шапка та же, предмет — ТС. */
export function buildCarInvoice(d) {
  const number = (d.invoiceNumber || "").trim() || `01-________`;
  const dateIso = d.invoiceDate || d.contractDate;
  const { blocks } = invoiceShell({
    number,
    dateIso,
    buyer: buyerLines(d).join(", "),
    itemName: carItemName(d),
    amount: carInvoiceAmount(d),
    vatMode: d.vatMode || "none",
  });
  return {
    kind: "invoice",
    logoSrc: INVOICE_LOGO_SRC,
    kicker: "",
    title: "",
    subtitle: [],
    meta: { city: "", date: "" },
    preamble: letterhead(d),
    blocks,
    signatures: directorSign(d),
  };
}
