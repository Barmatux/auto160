export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cellHtml(value) {
  return escapeHtml(value).replace(/\n/g, "<br />");
}

function blockHtml(block) {
  if (block.type === "heading") return `<h2 class="sheet-h">${escapeHtml(block.text)}</h2>`;
  if (block.type === "title") return `<h2 class="sheet-h center">${escapeHtml(block.text)}</h2>`;
  if (block.type === "p") {
    const cls = ["sheet-p", block.className].filter(Boolean).join(" ");
    return `<p class="${cls}">${cellHtml(block.text)}</p>`;
  }
  if (block.type === "note") return `<p class="sheet-note">${escapeHtml(block.text)}</p>`;
  if (block.type === "space") return `<div class="sheet-space"></div>`;
  if (block.type === "kv") {
    const rows = block.rows
      .map(
        ([k, v]) =>
          `<tr><th>${escapeHtml(k)}</th><td>${cellHtml(v)}</td></tr>`,
      )
      .join("");
    return `<table class="sheet-kv"><tbody>${rows}</tbody></table>`;
  }
  if (block.type === "table") {
    const head = block.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
    const body = block.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${cellHtml(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<table class="sheet-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  return "";
}

function signsHtml(sig) {
  if (!sig) return "";
  if (sig.mode === "single") {
    return `<div class="signs signs-single"><div class="sign-line-single">${escapeHtml(sig.line || "")}</div></div>`;
  }
  const col = (title, lines, role, sign) => `
    <div class="sign-col">
      <div class="sign-title">${escapeHtml(title)}</div>
      ${(lines || []).filter(Boolean).map((line) => `<div>${escapeHtml(line)}</div>`).join("")}
      <div class="sign-gap"></div>
      <div class="sign-role">${escapeHtml(role)}</div>
      <div class="sign-line">${escapeHtml(sign)}</div>
    </div>`;
  return `<div class="signs">${col(sig.leftTitle, sig.leftLines, sig.leftRole, sig.leftSign)}${col(
    sig.rightTitle,
    sig.rightLines,
    sig.rightRole,
    sig.rightSign,
  )}</div>`;
}

function preambleHtml(doc) {
  if (!doc.preamble && !doc.logoSrc) return "";
  const lines = String(doc.preamble || "")
    .split("\n")
    .filter((line) => line.length);
  let letterhead = "";
  if (lines.length <= 1 && doc.preamble) {
    letterhead = `<p class="sheet-p preamble">${escapeHtml(doc.preamble)}</p>`;
  } else if (lines.length) {
    letterhead = `<div class="sheet-letterhead">${lines
      .map((line) => `<div>${escapeHtml(line)}</div>`)
      .join("")}</div>`;
  }
  if (!doc.logoSrc) return letterhead;
  // Table layout so Word and PDF keep logo + requisites side by side (CSS grid breaks in Word).
  return `<table class="sheet-invoice-head" width="100%" cellpadding="0" cellspacing="0" style="border:0;border-collapse:collapse;margin-bottom:12pt;">
    <tr>
      <td width="120" valign="top" style="border:0;padding:0 12pt 0 0;width:120px;">
        <img class="sheet-invoice-logo" src="${escapeHtml(doc.logoSrc)}" alt="" width="110" height="75" />
      </td>
      <td valign="top" style="border:0;padding:0;">${letterhead}</td>
    </tr>
  </table>`;
}

/** Keep section heading with the next block so it never sits alone at page bottom. */
function blocksHtml(blocks) {
  const out = [];
  let i = 0;
  while (i < blocks.length) {
    const block = blocks[i];
    if (block.type === "heading") {
      const chunk = [blockHtml(block)];
      i += 1;
      if (i < blocks.length && blocks[i].type !== "heading") {
        chunk.push(blockHtml(blocks[i]));
        i += 1;
      }
      out.push(`<div class="sheet-keep">${chunk.join("")}</div>`);
      continue;
    }
    if (block.type === "title") {
      const chunk = [blockHtml(block)];
      i += 1;
      if (i < blocks.length && blocks[i].type !== "heading" && blocks[i].type !== "title") {
        chunk.push(blockHtml(blocks[i]));
        i += 1;
      }
      out.push(`<div class="sheet-keep">${chunk.join("")}</div>`);
      continue;
    }
    out.push(blockHtml(block));
    i += 1;
  }
  return out.join("");
}

export function renderSheet(doc, { pageBreakBefore = false } = {}) {
  const blocks = [...(doc.blocks || [])];
  const signs = signsHtml(doc.signatures);
  const last = blocks[blocks.length - 1];
  const lastIsRequisites =
    last?.type === "heading" && /РЕКВИЗИТЫ/i.test(String(last.text || ""));
  let body;
  if (lastIsRequisites) {
    const heading = blocks.pop();
    body = `${blocksHtml(blocks)}<div class="sheet-keep">${blockHtml(heading)}${signs}</div>`;
  } else if (blocks.length || signs) {
    body = `${blocksHtml(blocks)}${signs}`;
  } else {
    body = "";
  }
  const annexBlocks = [...(doc.annex1 || [])];
  const annexOnly = Boolean(doc.annex1) && !doc.title && !(doc.blocks || []).length && !doc.preamble;
  const annex = doc.annex1
    ? `<div class="sheet-annex${annexOnly ? " sheet-annex-only" : ""}">${blocksHtml(annexBlocks)}<div class="sheet-keep">${signsHtml(doc.signatures)}</div></div>`
    : "";
  const kicker = doc.kicker
    ? `<div class="sheet-kicker">${escapeHtml(doc.kicker)}</div>`
    : "";
  const title = doc.title
    ? `<h1 class="sheet-title">${escapeHtml(doc.title)}</h1>`
    : "";
  const subtitle = (doc.subtitle || [])
    .map((line) => `<p class="sheet-sub">${escapeHtml(line)}</p>`)
    .join("");
  const metaCity = doc.meta?.city || "";
  const metaDate = doc.meta?.date || "";
  const meta =
    metaCity || metaDate
      ? `<table class="sheet-meta" width="100%" cellpadding="0" cellspacing="0" style="border:0;border-collapse:collapse;margin:12pt 0;">
          <tr>
            <td style="border:0;padding:0;text-align:left;">${escapeHtml(metaCity)}</td>
            <td style="border:0;padding:0;text-align:right;">${escapeHtml(metaDate)}</td>
          </tr>
        </table>`
      : "";
  const breakCls = pageBreakBefore ? " sheet-break" : "";
  const breakMarker = pageBreakBefore
    ? `<br clear="all" style="page-break-before:always;mso-break-type:section-break;" />`
    : "";
  return `
    ${breakMarker}
    <article class="sheet sheet-${escapeHtml(doc.kind || "doc")}${breakCls}">
      ${kicker}
      ${title}
      ${subtitle}
      ${meta}
      ${preambleHtml(doc)}
      ${body}
      ${annex}
    </article>`;
}

export function renderSheets(docs) {
  return (docs || [])
    .filter(Boolean)
    .map((doc, index) => renderSheet(doc, { pageBreakBefore: index > 0 }))
    .join("");
}

async function urlToDataUrl(url) {
  if (!url || String(url).startsWith("data:")) return url || "";
  try {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) return url;
    const blob = await res.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return url;
  }
}

async function embedImagesInHtml(html) {
  const urls = [...html.matchAll(/<img[^>]+src="([^"]+)"/gi)].map((m) => m[1]);
  const unique = [...new Set(urls)].filter((u) => u && !u.startsWith("data:"));
  const map = new Map();
  await Promise.all(
    unique.map(async (url) => {
      map.set(url, await urlToDataUrl(url));
    }),
  );
  let out = html;
  for (const [url, data] of map) {
    out = out.split(url).join(data);
  }
  return out;
}

export async function downloadWord(docOrDocs, filename) {
  const docs = Array.isArray(docOrDocs) ? docOrDocs : [docOrDocs];
  let inner = await embedImagesInHtml(renderSheets(docs));
  const title = docs.map((d) => d?.title).filter(Boolean)[0] || "Документ";
  const html = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
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
    margin: 25mm 18mm 25mm 20mm;
    mso-header-margin: 10mm;
    mso-footer-margin: 12mm;
    mso-header: h1;
    mso-footer: f1;
    mso-paper-source: 0;
  }
  div.WordSection1 { page: WordSection1; }
  p.MsoHeader { margin: 0; font-size: 1pt; }
  p.MsoFooter {
    margin: 0;
    font-family: "Times New Roman", Times, serif;
    font-size: 10pt;
    text-align: center;
    color: #000;
  }
  body { font-family: "Times New Roman", Times, serif; font-size: 12pt; color: #000; }
  .sheet { width: auto; border: 0; padding: 0; color: #000; }
  .sheet-letterhead { margin-bottom: 10pt; line-height: 1.35; color: #000; }
  .sheet-kicker { text-align: center; font-size: 9pt; letter-spacing: .12em; text-transform: uppercase; color: #000; }
  .sheet-title {
    text-align: center;
    font-family: "Times New Roman", Times, serif;
    font-size: 14pt;
    font-weight: bold;
    margin: 6pt 0 4pt;
    color: #000;
  }
  .sheet-sub { text-align: center; font-style: italic; margin: 0; color: #000; }
  .sheet-meta { margin: 12pt 0; color: #000; }
  .sheet-h {
    font-size: 12pt;
    margin: 10pt 0 4pt;
    color: #000;
    page-break-after: avoid;
  }
  .sheet-h.center { text-align: center; }
  .sheet-keep { page-break-inside: avoid; }
  .sheet-p {
    text-align: justify;
    margin: 0;
    color: #000;
  }
  .sheet-note { font-size: 10pt; font-style: italic; color: #000; }
  table.sheet-kv, table.sheet-table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; }
  table.sheet-kv th, table.sheet-kv td,
  table.sheet-table th, table.sheet-table td {
    border: 1px solid #000; padding: 3pt 5pt; vertical-align: top; color: #000; background: #fff;
  }
  table.sheet-invoice-head, table.sheet-meta, table.sheet-invoice-head td, table.sheet-meta td {
    border: 0 !important;
  }
  .signs { display: table; width: 100%; margin-top: 18pt; page-break-inside: avoid; }
  .signs-single { display: block; margin-top: 28pt; }
  .sign-line-single { margin-top: 18pt; }
  .sign-col { display: table-cell; width: 50%; vertical-align: top; padding-right: 18pt; color: #000; }
  .sign-title { font-weight: bold; margin-bottom: 8pt; }
  .sign-role { color: #000; font-style: italic; }
  .sign-gap { height: 22pt; }
  .sheet-invoice-title { text-align: center; font-weight: bold; margin: 12pt 0 8pt; }
  .sheet-invoice-buyer { white-space: pre-line; margin: 0 0 10pt; }
  .sheet-invoice-logo { width: 90pt; height: auto; }
  .sheet-annex { page-break-before: always; padding-top: 12pt; }
  .sheet-break, .sheet-annex-only { page-break-before: always; }
</style>
</head>
<body>
<div style="mso-element:header" id="h1"><p class="MsoHeader">&nbsp;</p></div>
<div style="mso-element:footer" id="f1">
  <p class="MsoFooter" style="text-align:center">
    <!--[if supportFields]><span style="mso-element:field-begin"></span> PAGE <span style="mso-element:field-separator"></span><![endif]-->1<!--[if supportFields]><span style="mso-element:field-end"></span><![endif]-->
  </p>
</div>
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
