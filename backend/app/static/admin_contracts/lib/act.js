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

function formatDateShortSafe(iso) {
  if (!iso) return "____________";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return "____________";
  return `${d}.${m}.${y}`;
}

export function buildAct(d) {
  const vat = computeVat(d.amount, d.vatMode);
  const actNo = (d.actNumber || "").trim() || `${dash(d.contractNumber)}-А`;
  const period = `${formatDateLong(d.serviceFrom || d.contractDate)} — ${formatDateLong(d.serviceTo || d.actDate || d.contractDate)}`;
  const description = dash(
    d.serviceDescription,
    "Информационно-консультационные услуги по подбору транспортного средства",
  );
  const tableItem = [
    description,
    `Договор № ${dash(d.contractNumber)} от ${formatDateLong(d.contractDate)}`,
    `Период оказания услуг: ${period}`,
  ].join("\n");

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

  const costText =
    vat.rate > 0
      ? `1. Стоимость указанных услуг составила ${moneyPhrase(vat.gross)}, в том числе НДС ${vat.rate} % — ${moneyPhrase(vat.vat)}, сумма без НДС — ${moneyPhrase(vat.net)}.`
      : `1. Стоимость указанных услуг составила ${moneyPhrase(vat.gross)}. НДС не исчисляется.`;

  const blocks = [
    {
      type: "p",
      text: `Мы, нижеподписавшиеся, ${d.executorName}, УНП ${d.executorUnp} (Исполнитель), в лице директора ${d.executorDirectorGenitive}, действующего на основании Устава, и ${clientName(d)} (Заказчик), ${clientIdLine(d)}, составили настоящий акт о том, что Исполнитель оказал, а Заказчик принял следующие услуги:`,
    },
    {
      type: "table",
      columns: ["№", "Наименование услуги", "Ед. изм.", "Кол-во", "Цена, BYN", "Сумма, BYN"],
      rows: [["1", tableItem, "услуга", "1", formatAmount(vat.net), formatAmount(vat.net)]],
    },
    { type: "kv", rows: vatRows },
    { type: "p", text: costText },
    {
      type: "p",
      text: "2. Услуги оказаны полностью, в согласованном объёме и в установленный договором срок. Заказчик претензий по объёму, качеству и срокам оказания услуг на дату подписания акта не имеет.",
    },
    {
      type: "p",
      text: "3. Акт составлен в двух экземплярах, имеющих одинаковую юридическую силу, по одному для Исполнителя и Заказчика.",
    },
  ];

  return {
    kind: "act",
    kicker: "",
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
