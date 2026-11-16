export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function blockHtml(block) {
  if (block.type === "heading") return `<h2 class="sheet-h">${escapeHtml(block.text)}</h2>`;
  if (block.type === "title") return `<h2 class="sheet-h center">${escapeHtml(block.text)}</h2>`;
  if (block.type === "p") return `<p class="sheet-p">${escapeHtml(block.text)}</p>`;
  if (block.type === "note") return `<p class="sheet-note">${escapeHtml(block.text)}</p>`;
  if (block.type === "space") return `<div class="sheet-space"></div>`;
  if (block.type === "kv") {
    const rows = block.rows
      .map(
        ([k, v]) =>
          `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`,
      )
      .join("");
    return `<table class="sheet-kv"><tbody>${rows}</tbody></table>`;
  }
  if (block.type === "table") {
    const head = block.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
    const body = block.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<table class="sheet-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  return "";
}

function signsHtml(sig) {
  const col = (title, lines, role, sign) => `
    <div class="sign-col">
      <div class="sign-title">${escapeHtml(title)}</div>
      ${lines.filter(Boolean).map((line) => `<div>${escapeHtml(line)}</div>`).join("")}
      <div class="sign-gap"></div>
      <div class="sign-role">${escapeHtml(role)}</div>
      <div class="sign-line">${escapeHtml(sign)}</div>
      <div class="sign-stamp">М.П. (при использовании печати)</div>
    </div>`;
  return `<div class="signs">${col(sig.leftTitle, sig.leftLines, sig.leftRole, sig.leftSign)}${col(
    sig.rightTitle,
    sig.rightLines,
    sig.rightRole,
    sig.rightSign,
  )}</div>`;
}

function preambleHtml(doc) {
  if (!doc.preamble) return "";
  const lines = String(doc.preamble).split("\n").filter((line) => line.length);
  if (lines.length <= 1) {
    return `<p class="sheet-p preamble">${escapeHtml(doc.preamble)}</p>`;
  }
  return `<div class="sheet-letterhead">${lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("")}</div>`;
}

export function renderSheet(doc) {
  const annex = doc.annex1
    ? `<div class="sheet-annex">${doc.annex1.map(blockHtml).join("")}${signsHtml(doc.signatures)}</div>`
    : "";
  return `
    <article class="sheet sheet-${escapeHtml(doc.kind || "doc")}">
      <div class="sheet-kicker">${escapeHtml(doc.kicker)}</div>
      <h1 class="sheet-title">${escapeHtml(doc.title)}</h1>
      ${doc.subtitle.map((line) => `<p class="sheet-sub">${escapeHtml(line)}</p>`).join("")}
      <div class="sheet-meta"><span>${escapeHtml(doc.meta.city)}</span><span>${escapeHtml(doc.meta.date)}</span></div>
      ${preambleHtml(doc)}
      ${doc.blocks.map(blockHtml).join("")}
      ${signsHtml(doc.signatures)}
      ${annex}
    </article>`;
}

export function downloadWord(doc, filename) {
  const inner = renderSheet(doc);
  const html = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(doc.title)}</title>
<!--[if gte mso 9]>
<xml>
<w:WordDocument>
  <w:View>Print</w:View>
  <w:Zoom>100</w:Zoom>
  <w:DoNotOptimizeForBrowser/>
</w:WordDocument>
</xml>
<![endif]-->
<style>
  @page WordSection1 {
    size: 210mm 297mm;
    margin: 20mm 18mm 18mm 20mm;
    mso-header-margin: 0mm;
    mso-footer-margin: 0mm;
    mso-header: h1;
    mso-footer: f1;
    mso-paper-source: 0;
  }
  div.WordSection1 { page: WordSection1; }
  p.MsoHeader, p.MsoFooter { margin: 0; font-size: 1pt; }
  body { font-family: "Times New Roman", Times, serif; font-size: 12pt; color: #1c1916; }
  .sheet { width: auto; border: 0; padding: 0; }
  .sheet-letterhead { margin-bottom: 12pt; line-height: 1.35; }
  .sheet-kicker { text-align: center; font-size: 9pt; letter-spacing: .12em; text-transform: uppercase; }
  .sheet-title { text-align: center; font-size: 18pt; margin: 8pt 0; }
  .sheet-sub { text-align: center; font-style: italic; margin: 0; }
  .sheet-meta { display: flex; justify-content: space-between; margin: 16pt 0; }
  .sheet-h { font-size: 12pt; margin: 14pt 0 8pt; }
  .sheet-h.center { text-align: center; }
  .sheet-p { text-align: justify; margin: 0 0 8pt; }
  .sheet-note { font-size: 10pt; font-style: italic; color: #555; }
  table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt; }
  th, td { border: 1px solid #c4b49a; padding: 4pt 6pt; vertical-align: top; }
  th { background: #efe8dc; text-align: left; }
  .signs { display: table; width: 100%; margin-top: 24pt; }
  .sign-col { display: table-cell; width: 50%; vertical-align: top; padding-right: 18pt; }
  .sign-title { font-weight: bold; margin-bottom: 8pt; }
  .sign-gap { height: 22pt; }
  .sheet-annex { page-break-before: always; padding-top: 12pt; }
</style>
</head>
<body>
<div style="mso-element:header" id="h1"><p class="MsoHeader">&nbsp;</p></div>
<div style="mso-element:footer" id="f1"><p class="MsoFooter">&nbsp;</p></div>
<div class="WordSection1">${inner}</div>
</body>
</html>`;
  const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".doc") ? filename : `${filename}.doc`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
