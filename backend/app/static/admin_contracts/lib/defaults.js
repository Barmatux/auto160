import { suggestContractNumber, suggestInvoiceNumber, todayIso } from "./format.js";

export const BY_SERVICE =
  "Информационно-консультационные услуги по поиску и подбору транспортного средства на рынке Республики Беларусь";
export const EU_SERVICE =
  "Информационно-консультационные услуги по подбору транспортного средства на рынке Европейского союза и информационному сопровождению его приобретения";

export function applyPackageDefaults(data) {
  const by = (data.packageType || "by") !== "eu";
  const date = data.contractDate || todayIso();
  return {
    ...data,
    marketplace: by
      ? data.marketplace && !/ЕС|аукцион/i.test(data.marketplace)
        ? data.marketplace
        : "av.by, дилеры, автосалоны и частные объявления Республики Беларусь"
      : data.marketplace && /ЕС|аукцион/i.test(data.marketplace)
        ? data.marketplace
        : "аукционы и дилерские площадки ЕС",
    vehicleBudgetCurrency: by ? data.vehicleBudgetCurrency || "BYN" : data.vehicleBudgetCurrency || "EUR",
    serviceDescription: by ? BY_SERVICE : EU_SERVICE,
    contractNumber: suggestContractNumber(date, by ? "Б" : "П"),
    invoiceNumber: data.invoiceNumber || suggestInvoiceNumber(date),
  };
}

export function createDefaultData() {
  const date = todayIso();
  return applyPackageDefaults({
    packageType: "by",
    contractNumber: suggestContractNumber(date, "Б"),
    contractDate: date,
    invoiceNumber: suggestInvoiceNumber(date),
    invoiceDate: date,
    city: "Минск",

    clientType: "individual",
    gender: "male",
    clientName: "",
    clientAddress: "",
    passport: "",
    passportIssuer: "",
    passportDate: "",
    personalNumber: "",
    clientPhone: "",
    clientEmail: "",
    clientMessenger: "Viber / Telegram / WhatsApp",

    clientCompany: "",
    clientUnp: "",
    clientDirector: "",
    clientDirectorGenitive: "",
    clientBasis: "Устава",
    clientBankDetails: "",

    amount: "1000",
    vatMode: "none",
    prepaidDays: "5",
    invoicePayDays: "2",
    bidReplyTime: "17:00",
    refundDays: "15",
    actReviewDays: "5",
    penaltyPercent: "10",

    vehicleMake: "",
    vehicleModel: "",
    vehicleYearFrom: "",
    vehicleYearTo: "",
    vehicles: [{ make: "", model: "", yearFrom: "", yearTo: "" }],
    vehicleBudget: "",
    vehicleBudgetCurrency: "BYN",
    marketplace: "av.by, дилеры, автосалоны и частные объявления Республики Беларусь",
    vehicleNotes: "",
    mileageMax: "",
    fuel: "",
    engineVolume: "",
    transmission: "",
    color: "",
    vehicleVin: "",

    invoiceAmount: "",
    invoiceCarMake: "",
    invoiceCarModel: "",
    invoiceCarYear: "",
    invoiceCarVin: "",

    actNumber: "",
    actDate: date,
    serviceFrom: date,
    serviceTo: date,
    serviceDescription: BY_SERVICE,

    photoConsent: false,

    executorName: "Общество с ограниченной ответственностью «Сканди Моторс»",
    executorShort: "ООО «Сканди Моторс»",
    executorUnp: "193866357",
    executorAddress: "г. Минск, ул. Скрыганова, дом 6, помещение 7",
    executorEmail: "scandimotorsby@gmail.com",
    executorPhone: "+375 (33) 698-77-99",
    executorDirector: "Герасимец Максим Сергеевич",
    executorDirectorShort: "Герасимец М.С.",
    executorDirectorGenitive: "Герасимца Максима Сергеевича",
    executorAccount: "BY58 ALFA 3012 2G91 3900 1027 0000",
    executorBank: "ЗАО «Альфа-Банк», 220013, г. Минск, ул. Сурганова, 43-47",
    executorSwift: "ALFABY2X",
    executorBankUnp: "101541947",
    executorOkpo: "37526626",
  });
}

/** Keep legacy make/model/year fields in sync; migrate old drafts into vehicles[]. */
export function normalizeContractData(data) {
  const next = { ...data };
  if (Array.isArray(next.vehicles) && next.vehicles.length) {
    next.vehicles = next.vehicles.map((row) => ({
      make: row?.make || "",
      model: row?.model || "",
      yearFrom: row?.yearFrom || "",
      yearTo: row?.yearTo || "",
    }));
  } else {
    next.vehicles = [
      {
        make: next.vehicleMake || "",
        model: next.vehicleModel || "",
        yearFrom: next.vehicleYearFrom || "",
        yearTo: next.vehicleYearTo || "",
      },
    ];
  }
  const first = next.vehicles[0] || { make: "", model: "", yearFrom: "", yearTo: "" };
  next.vehicleMake = first.make;
  next.vehicleModel = first.model;
  next.vehicleYearFrom = first.yearFrom;
  next.vehicleYearTo = first.yearTo;
  if (!String(next.invoiceCarMake || "").trim()) next.invoiceCarMake = next.vehicleMake || "";
  if (!String(next.invoiceCarModel || "").trim()) next.invoiceCarModel = next.vehicleModel || "";
  if (!String(next.invoiceCarYear || "").trim()) {
    next.invoiceCarYear = next.vehicleYearFrom || next.vehicleYearTo || "";
  }
  if (!String(next.invoiceCarVin || "").trim()) next.invoiceCarVin = next.vehicleVin || "";
  return next;
}

export const SAMPLE_CLIENT = {
  clientType: "individual",
  gender: "male",
  clientName: "Каржицкий Александр Сергеевич",
  clientAddress: "Витебская обл., г. Орша, ул. Владимира Ленина, д. 63, кв. 55",
  passport: "BM1964183",
  passportIssuer: "Октябрьским РОВД г. Орши",
  passportDate: "2012-01-26",
  personalNumber: "3241286E025PB7",
  clientPhone: "+375 (33) 647-47-10",
  clientEmail: "",
  clientMessenger: "Viber",
  amount: "1000",
  vehicleMake: "",
  vehicleModel: "",
  vehicleBudget: "",
  marketplace: "av.by, дилеры, автосалоны и частные объявления Республики Беларусь",
};
