function plural(n, one, few, many) {
  const n100 = Math.abs(n) % 100;
  const n10 = n100 % 10;
  if (n100 >= 11 && n100 <= 14) return many;
  if (n10 === 1) return one;
  if (n10 >= 2 && n10 <= 4) return few;
  return many;
}

const ONES_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"];
const ONES_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"];
const TEENS = [
  "десять",
  "одиннадцать",
  "двенадцать",
  "тринадцать",
  "четырнадцать",
  "пятнадцать",
  "шестнадцать",
  "семнадцать",
  "восемнадцать",
  "девятнадцать",
];
const TENS = [
  "",
  "",
  "двадцать",
  "тридцать",
  "сорок",
  "пятьдесят",
  "шестьдесят",
  "семьдесят",
  "восемьдесят",
  "девяносто",
];
const HUNDREDS = [
  "",
  "сто",
  "двести",
  "триста",
  "четыреста",
  "пятьсот",
  "шестьсот",
  "семьсот",
  "восемьсот",
  "девятьсот",
];

function triadToWords(n, gender) {
  const ones = gender === "f" ? ONES_F : ONES_M;
  const h = Math.floor(n / 100);
  const t = n % 100;
  const parts = [];
  if (h) parts.push(HUNDREDS[h]);
  if (t >= 10 && t <= 19) {
    parts.push(TEENS[t - 10]);
  } else {
    const ten = Math.floor(t / 10);
    const one = t % 10;
    if (ten) parts.push(TENS[ten]);
    if (one) parts.push(ones[one]);
  }
  return parts.join(" ");
}

export function integerToWords(n, gender = "m") {
  n = Math.floor(Math.abs(n));
  if (n === 0) return "ноль";

  const groups = [
    { value: 1_000_000_000, gender: "m", one: "миллиард", few: "миллиарда", many: "миллиардов" },
    { value: 1_000_000, gender: "m", one: "миллион", few: "миллиона", many: "миллионов" },
    { value: 1_000, gender: "f", one: "тысяча", few: "тысячи", many: "тысяч" },
    { value: 1, gender, one: "", few: "", many: "" },
  ];

  const parts = [];
  for (const g of groups) {
    const count = Math.floor(n / g.value);
    n %= g.value;
    if (!count) continue;
    const words = triadToWords(count, g.gender);
    if (g.one) {
      parts.push(`${words} ${plural(count, g.one, g.few, g.many)}`);
    } else {
      parts.push(words);
    }
  }
  return parts.join(" ").replace(/\s+/g, " ").trim();
}

export function parseMoney(value) {
  if (value === null || value === undefined) return { rubles: 0, kopecks: 0, total: 0 };
  const normalized = String(value).replace(/\s/g, "").replace(",", ".");
  const num = Number(normalized);
  if (!Number.isFinite(num) || num < 0) return { rubles: 0, kopecks: 0, total: 0 };
  const totalKopecks = Math.round(num * 100);
  return {
    rubles: Math.floor(totalKopecks / 100),
    kopecks: totalKopecks % 100,
    total: totalKopecks / 100,
  };
}

export function formatAmount(value) {
  const { total } = parseMoney(value);
  return total.toLocaleString("ru-BY", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function moneyToWords(value) {
  const { rubles, kopecks } = parseMoney(value);
  const rubWords = integerToWords(rubles, "m");
  const rubUnit = plural(rubles, "белорусский рубль", "белорусских рубля", "белорусских рублей");
  const kopWords = integerToWords(kopecks, "f");
  const kopUnit = plural(kopecks, "копейка", "копейки", "копеек");
  return `${rubWords} ${rubUnit} ${String(kopecks).padStart(2, "0")} (${kopWords}) ${kopUnit}`;
}

export function moneyPhrase(value) {
  const { rubles, kopecks } = parseMoney(value);
  const words = integerToWords(rubles, "m");
  const unit = plural(rubles, "белорусский рубль", "белорусских рубля", "белорусских рублей");
  return `${rubles.toLocaleString("ru-BY")} (${words}) ${unit}${
    kopecks ? ` ${String(kopecks).padStart(2, "0")} копеек` : ""
  }`;
}

export function computeVat(amount, vatMode) {
  const { total } = parseMoney(amount);
  if (vatMode === "included20") {
    const net = Math.round((total / 1.2) * 100) / 100;
    const vat = Math.round((total - net) * 100) / 100;
    return { net, vat, gross: total, rate: 20, label: "НДС 20 % включён в стоимость" };
  }
  if (vatMode === "onTop20") {
    const vat = Math.round(total * 0.2 * 100) / 100;
    return { net: total, vat, gross: Math.round((total + vat) * 100) / 100, rate: 20, label: "НДС 20 % сверх стоимости" };
  }
  return { net: total, vat: 0, gross: total, rate: 0, label: "НДС не исчисляется" };
}
