import { dash, formatDateLong, initialsFromFullName } from "./format.js";
import { computeVat, formatAmount, moneyPhrase } from "./money.js";

function clientName(d) {
  return d.clientType === "legal" ? dash(d.clientCompany) : dash(d.clientName);
}

function clientIdLine(d) {
  if (d.clientType === "legal") {
    return `УНП ${dash(d.clientUnp, "_________")}, адрес: ${dash(d.clientAddress)}`;
  }
  const bits = [`адрес: ${dash(d.clientAddress)}`];
  if (d.passport) bits.push(`паспорт ${d.passport}`);
  if (d.personalNumber) bits.push(`идентификационный номер ${d.personalNumber}`);
  return bits.join(", ");
}

export function buildAct(d) {
  const vat = computeVat(d.amount, d.vatMode);
  const actNo = (d.actNumber || "").trim() || `${dash(d.contractNumber)}-А`;
  const period = `${formatDateLong(d.serviceFrom || d.contractDate)} — ${formatDateLong(d.serviceTo || d.actDate || d.contractDate)}`;
  const description = dash(
    d.serviceDescription,
    "Информационно-консультационные услуги по подбору транспортного средства",
  );

  const vatRows =
    vat.rate > 0
      ? [
          ["Сумма без НДС", `${formatAmount(vat.net)} BYN`],
          [`НДС ${vat.rate} %`, `${formatAmount(vat.vat)} BYN`],
          ["Всего с НДС", `${formatAmount(vat.gross)} BYN`],
        ]
      : [
          ["Ставка НДС", "не исчисляется"],
          ["Всего", `${formatAmount(vat.gross)} BYN`],
        ];

  const blocks = [
    {
      type: "p",
      text: `Мы, нижеподписавшиеся, ${d.executorName}, УНП ${d.executorUnp} (Исполнитель), в лице директора ${d.executorDirectorGenitive}, действующего на основании Устава, и ${clientName(d)} (Заказчик), ${clientIdLine(d)}, составили настоящий акт о нижеследующем.`,
    },
    {
      type: "p",
      text: `1. Основание хозяйственной операции: договор возмездного оказания информационно-консультационных услуг по подбору транспортного средства № ${dash(d.contractNumber)} от ${formatDateLong(d.contractDate)}`,
    },
    {
      type: "p",
      text: `2. Период оказания услуг: ${period}`,
    },
    {
      type: "p",
      text: "3. Исполнитель оказал, а Заказчик принял следующие услуги:",
    },
    {
      type: "table",
      columns: ["№", "Наименование услуги", "Ед. изм.", "Кол-во", "Цена, BYN", "Сумма, BYN"],
      rows: [["1", description, "услуга", "1", formatAmount(vat.net), formatAmount(vat.net)]],
    },
    { type: "kv", rows: vatRows },
    {
      type: "p",
      text: `4. Оценка операции: услуги оказаны в натуральном показателе — 1 (одна) услуга; в стоимостном показателе — ${moneyPhrase(vat.gross)}${vat.rate ? `, в том числе НДС ${moneyPhrase(vat.vat)}` : ", НДС не исчисляется"}.`,
    },
    {
      type: "p",
      text: "5. Услуги оказаны полностью, в согласованном объёме и в установленный договором срок. Заказчик претензий по объёму, качеству и срокам оказания услуг на дату подписания акта не имеет.",
    },
    {
      type: "p",
      text: "6. Настоящий акт является первичным учётным документом и содержит сведения, предусмотренные пунктом 2 статьи 10 Закона Республики Беларусь от 12 июля 2013 г. № 57-З «О бухгалтерском учёте и отчётности»: наименование и дату составления; сведения об участниках операции; содержание и основание операции, её оценку; должности, фамилии, инициалы и подписи лиц, ответственных за совершение операции и правильность её оформления.",
    },
    {
      type: "p",
      text: "7. Акт составлен в двух экземплярах, имеющих одинаковую юридическую силу, по одному для Исполнителя и Заказчика.",
    },
    {
      type: "note",
      text: "Унифицированная форма акта для данного вида услуг законодательством Республики Беларусь не установлена (исключение — строительство). Форма разработана Исполнителем и согласована сторонами договором. Акт рекомендуется закрепить в учётной политике Исполнителя.",
    },
  ];

  return {
    kind: "act",
    kicker: "Первичный учётный документ · ст. 10 Закона № 57-З",
    title: `АКТ № ${actNo}`,
    subtitle: ["сдачи-приёмки оказанных услуг", `(к договору № ${dash(d.contractNumber)} от ${formatDateShortSafe(d.contractDate)})`],
    meta: { city: `г. ${dash(d.city, "Минск")}`, date: formatDateLong(d.actDate || d.contractDate) },
    preamble: "",
    blocks,
    signatures: {
      leftTitle: "ИСПОЛНИТЕЛЬ",
      rightTitle: "ЗАКАЗЧИК",
      leftLines: [
        d.executorShort,
        `УНП ${d.executorUnp}`,
        d.executorAddress,
        "Должность: директор",
        d.executorDirector,
      ],
      rightLines:
        d.clientType === "legal"
          ? [dash(d.clientCompany), d.clientUnp ? `УНП ${d.clientUnp}` : "", dash(d.clientAddress, ""), dash(d.clientDirector, "")]
          : [dash(d.clientName), dash(d.clientAddress, ""), d.passport ? `паспорт ${d.passport}` : "", "Заказчик"],
      leftSign: `________________ / ${d.executorDirectorShort} /`,
      rightSign: `________________ / ${
        d.clientType === "legal"
          ? initialsFromFullName(d.clientDirector) || dash(d.clientCompany)
          : initialsFromFullName(d.clientName) || "____________________"
      } /`,
      leftRole: "Директор",
      rightRole: d.clientType === "legal" ? "Руководитель" : "Заказчик",
    },
  };
}

function formatDateShortSafe(iso) {
  if (!iso) return "____________";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return "____________";
  return `${d}.${m}.${y}`;
}
