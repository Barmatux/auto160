import { dash, formatDateLong, formatDateShort, initialsFromFullName } from "./format.js";
import { computeVat, formatAmount, moneyToWords } from "./money.js";
import { isByPackage } from "./contract.js";

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

function serviceName(d) {
  if ((d.serviceDescription || "").trim()) return d.serviceDescription.trim();
  if (isByPackage(d)) {
    return "Информационно-консультационные услуги по поиску и подбору транспортного средства на рынке Республики Беларусь";
  }
  return "Информационно-консультационные услуги по подбору транспортного средства на рынке Европейского союза";
}

export function buildInvoice(d) {
  const vat = computeVat(d.amount, d.vatMode);
  const number = (d.invoiceNumber || "").trim() || `С-${dash(d.contractNumber)}`;
  const dateIso = d.invoiceDate || d.contractDate;
  const vatCell = vat.rate ? formatAmount(vat.vat) : "Без НДС";
  const unitPrice = vat.rate ? formatAmount(vat.net) : formatAmount(vat.gross);
  const withVat = formatAmount(vat.gross);

  const blocks = [
    {
      type: "p",
      text: `Плательщик (покупатель): ${buyerLines(d).join("; ")}`,
    },
    {
      type: "p",
      text: `Основание: договор № ${dash(d.contractNumber)} от ${formatDateShort(d.contractDate)}. Срок оплаты: ${dash(d.prepaidDays, "5")} рабочих дней с даты счёта.`,
    },
    {
      type: "table",
      columns: [
        "№",
        "Наименование товара, услуги",
        "Кол-во",
        "Цена, руб. коп.",
        "НДС, руб. коп.",
        "Цена с НДС, руб. коп.",
        "Всего к оплате, руб. коп.",
      ],
      rows: [["1", serviceName(d), "1", unitPrice, vatCell, withVat, withVat]],
    },
    {
      type: "p",
      text: `Итого к оплате: ${formatAmount(vat.gross)} руб. (${moneyToWords(vat.gross)}).`,
    },
    {
      type: "note",
      text:
        vat.rate > 0
          ? `В том числе НДС ${vat.rate} % — ${formatAmount(vat.vat)} руб.`
          : "НДС не исчисляется. Счёт выставлен за услуги подбора, а не за продажу автомобиля. Цена ТС в сумму счёта не входит.",
    },
    {
      type: "p",
      text: "Оплата производится на расчётный счёт Исполнителя, указанный в шапке счёта. Назначение платежа: оплата услуг по подбору ТС, номер договора и счёта.",
    },
  ];

  return {
    kind: "invoice",
    kicker: `${d.executorShort} · УНП ${d.executorUnp}`,
    title: `СЧЁТ № ${number}`,
    subtitle: [`на оплату услуг`, `от ${formatDateLong(dateIso)}`],
    meta: { city: `г. ${dash(d.city, "Минск")}`, date: formatDateLong(dateIso) },
    preamble: [
      d.executorName,
      `Юридический адрес: ${d.executorAddress}`,
      `УНП: ${d.executorUnp}`,
      `Тел (Viber / WhatsApp / Telegram): ${d.executorPhone}`,
      d.executorEmail,
      `Р/с ${d.executorAccount} в BYN`,
      d.executorBank,
      `SWIFT ${d.executorSwift}, УНП банка ${d.executorBankUnp}, ОКПО ${d.executorOkpo}`,
    ].join("\n"),
    blocks,
    signatures: {
      leftTitle: "ИСПОЛНИТЕЛЬ",
      rightTitle: "ПЛАТЕЛЬЩИК",
      leftLines: [d.executorShort, `УНП ${d.executorUnp}`, d.executorAddress],
      rightLines: buyerLines(d),
      leftSign: `________________ / ${d.executorDirectorShort} /`,
      rightSign: `________________ / ${
        d.clientType === "legal"
          ? initialsFromFullName(d.clientDirector) || dash(d.clientCompany)
          : initialsFromFullName(d.clientName) || "____________________"
      } /`,
      leftRole: "Директор",
      rightRole: "Заказчик",
    },
  };
}
