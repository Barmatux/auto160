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

function blockHtml(block, { word = false } = {}) {
  if (block.type === "heading") return `<h2 class="sheet-h">${escapeHtml(block.text)}</h2>`;
  if (block.type === "title") return `<h2 class="sheet-h center">${escapeHtml(block.text)}</h2>`;
  if (block.type === "p") {
    const cls = ["sheet-p", block.className].filter(Boolean).join(" ");
    return `<p class="${cls}">${cellHtml(block.text)}</p>`;
  }
  if (block.type === "note") return `<p class="sheet-note">${escapeHtml(block.text)}</p>`;
  if (block.type === "space") {
    return word ? `<p class="sheet-space">&nbsp;</p>` : `<div class="sheet-space"></div>`;
  }
  if (block.type === "kv") {
    const rows = block.rows
      .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${cellHtml(v)}</td></tr>`)
      .join("");
    if (word) {
      return `<table class="sheet-kv" border="1" cellspacing="0" cellpadding="4" width="100%"><tbody>${rows}</tbody></table>`;
    }
    return `<table class="sheet-kv"><tbody>${rows}</tbody></table>`;
  }
  if (block.type === "table") {
    const head = block.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
    const body = block.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${cellHtml(cell)}</td>`).join("")}</tr>`)
      .join("");
    if (word) {
      return `<table class="sheet-table" border="1" cellspacing="0" cellpadding="4" width="100%"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }
    return `<table class="sheet-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  return "";
}

function signsHtml(sig, { word = false } = {}) {
  if (!sig) return "";
  if (sig.mode === "single") {
    return word
      ? `<p class="sign-line-single">${escapeHtml(sig.line || "")}</p>`
      : `<div class="signs signs-single"><div class="sign-line-single">${escapeHtml(sig.line || "")}</div></div>`;
  }
  if (word) {
    const col = (title, lines, role, sign) => `
      <td width="50%" valign="top" style="border:0;padding:0 18pt 0 0;">
        <p class="sign-title"><b>${escapeHtml(title)}</b></p>
        ${(lines || [])
          .filter(Boolean)
          .map((line) => `<p class="sign-line-text">${escapeHtml(line)}</p>`)
          .join("")}
        <p class="sign-gap">&nbsp;</p>
        <p class="sign-role"><i>${escapeHtml(role)}</i></p>
        <p class="sign-line">${escapeHtml(sign)}</p>
      </td>`;
    return `<table class="signs" border="0" cellspacing="0" cellpadding="0" width="100%" style="border:0;margin-top:18pt;">
      <tr>
        ${col(sig.leftTitle, sig.leftLines, sig.leftRole, sig.leftSign)}
        ${col(sig.rightTitle, sig.rightLines, sig.rightRole, sig.rightSign)}
      </tr>
    </table>`;
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

function preambleHtml(doc, { word = false } = {}) {
  if (!doc.preamble && !doc.logoSrc) return "";
  const lines = String(doc.preamble || "")
    .split("\n")
    .filter((line) => line.length);
  let letterhead = "";
  if (lines.length <= 1 && doc.preamble) {
    letterhead = `<p class="sheet-p preamble">${escapeHtml(doc.preamble)}</p>`;
  } else if (lines.length) {
    letterhead = word
      ? `<div class="sheet-letterhead">${lines
          .map((line) => `<p class="letter-line">${escapeHtml(line)}</p>`)
          .join("")}</div>`
      : `<div class="sheet-letterhead">${lines
          .map((line) => `<div>${escapeHtml(line)}</div>`)
          .join("")}</div>`;
  }
  if (!doc.logoSrc) return letterhead;
  // Smaller logo for Word — large PNG otherwise blows up the page layout.
  const logo = word
    ? `<img class="sheet-invoice-logo" src="${escapeHtml(doc.logoSrc)}" alt="" width="90" height="62" />`
    : `<img class="sheet-invoice-logo" src="${escapeHtml(doc.logoSrc)}" alt="" width="110" height="75" />`;
  return `<table class="sheet-invoice-head" border="0" width="100%" cellpadding="0" cellspacing="0" style="border:0;border-collapse:collapse;margin-bottom:12pt;">
    <tr>
      <td width="100" valign="top" style="border:0;padding:0 12pt 0 0;width:100px;">${logo}</td>
      <td valign="top" style="border:0;padding:0;">${letterhead}</td>
    </tr>
  </table>`;
}

/** Keep section heading with the next block so it never sits alone at page bottom. */
function blocksHtml(blocks, opts = {}) {
  const out = [];
  let i = 0;
  while (i < blocks.length) {
    const block = blocks[i];
    if (block.type === "heading") {
      const chunk = [blockHtml(block, opts)];
      i += 1;
      if (i < blocks.length && blocks[i].type !== "heading") {
        chunk.push(blockHtml(blocks[i], opts));
        i += 1;
      }
      // Word: rely on page-break-after:avoid on headings — keep-together on large
      // chunks leaves huge blank regions when Word cannot fit the block.
      out.push(opts.word ? chunk.join("") : `<div class="sheet-keep">${chunk.join("")}</div>`);
      continue;
    }
    if (block.type === "title") {
      const chunk = [blockHtml(block, opts)];
      i += 1;
      if (i < blocks.length && blocks[i].type !== "heading" && blocks[i].type !== "title") {
        chunk.push(blockHtml(blocks[i], opts));
        i += 1;
      }
      out.push(opts.word ? chunk.join("") : `<div class="sheet-keep">${chunk.join("")}</div>`);
      continue;
    }
    out.push(blockHtml(block, opts));
    i += 1;
  }
  return out.join("");
}

export function renderSheet(doc, { pageBreakBefore = false, word = false } = {}) {
  const opts = { word };
  const blocks = [...(doc.blocks || [])];
  const annexBlocks = [...(doc.annex1 || [])];
  const annexOnly = Boolean(doc.annex1) && !doc.title && !(doc.blocks || []).length && !doc.preamble;
  const signs = signsHtml(doc.signatures, opts);
  const last = blocks[blocks.length - 1];
  const lastIsRequisites =
    last?.type === "heading" && /РЕКВИЗИТЫ/i.test(String(last.text || ""));
  let body;
  if (annexOnly) {
    // Annex-only sheet: content + signs live inside .sheet-annex. Do not also
    // emit body signs — that orphaned a signature page before the annex break.
    body = "";
  } else if (lastIsRequisites) {
    const heading = blocks.pop();
    body = word
      ? `${blocksHtml(blocks, opts)}${blockHtml(heading, opts)}${signs}`
      : `${blocksHtml(blocks, opts)}<div class="sheet-keep">${blockHtml(heading, opts)}${signs}</div>`;
  } else if (blocks.length || signs) {
    body = `${blocksHtml(blocks, opts)}${signs}`;
  } else {
    body = "";
  }
  // Word pack already inserts one page-break marker before each subsequent doc.
  // Extra CSS page-break on .sheet-annex / .sheet-annex-only / .sheet-break stacked
  // into blank pages — so Word CSS drops those, and embedded annex gets one marker.
  const annexBreak =
    word && doc.annex1 && !annexOnly
      ? `<br clear="all" style="page-break-before:always;" />`
      : "";
  const annexSigns = word ? signsHtml(doc.signatures, opts) : `<div class="sheet-keep">${signsHtml(doc.signatures, opts)}</div>`;
  const annex = doc.annex1
    ? `${annexBreak}<div class="sheet-annex${annexOnly ? " sheet-annex-only" : ""}">${blocksHtml(annexBlocks, opts)}${annexSigns}</div>`
    : "";
  const kicker = doc.kicker
    ? word
      ? `<p class="sheet-kicker">${escapeHtml(doc.kicker)}</p>`
      : `<div class="sheet-kicker">${escapeHtml(doc.kicker)}</div>`
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
      ? `<table class="sheet-meta" border="0" width="100%" cellpadding="0" cellspacing="0" style="border:0;border-collapse:collapse;margin:12pt 0;">
          <tr>
            <td style="border:0;padding:0;text-align:left;">${escapeHtml(metaCity)}</td>
            <td style="border:0;padding:0;text-align:right;">${escapeHtml(metaDate)}</td>
          </tr>
        </table>`
      : "";
  // Keep sheet-break class for PDF capture CSS; Word stylesheet ignores it.
  const breakCls = pageBreakBefore ? " sheet-break" : "";
  // One ordinary break only. Avoid mso section-break and stacking with CSS breaks.
  const breakMarker = pageBreakBefore
    ? `<br clear="all" style="page-break-before:always;" />`
    : "";
  const tag = word ? "div" : "article";
  return `
    ${breakMarker}
    <${tag} class="sheet sheet-${escapeHtml(doc.kind || "doc")}${breakCls}">
      ${kicker}
      ${title}
      ${subtitle}
      ${meta}
      ${preambleHtml(doc, opts)}
      ${body}
      ${annex}
    </${tag}>`;
}

export function renderSheets(docs, { word = false } = {}) {
  return (docs || [])
    .filter(Boolean)
    .map((doc, index) => renderSheet(doc, { pageBreakBefore: index > 0, word }))
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
  let inner = await embedImagesInHtml(renderSheets(docs, { word: true }));
  const title = docs.map((d) => d?.title).filter(Boolean)[0] || "Документ";
  const html = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8" />
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
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
  /* Word-oriented styles: avoid flex/grid/display:table — Word ignores or mangels them. */
  @page WordSection1 {
    size: 210mm 297mm;
    margin: 20mm 18mm 20mm 18mm;
    mso-header-margin: 10mm;
    mso-footer-margin: 12mm;
    mso-header: h1;
    mso-footer: f1;
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
  body {
    font-family: "Times New Roman", Times, serif;
    font-size: 12pt;
    line-height: 1.35;
    color: #000;
    margin: 0;
  }
  .sheet { width: 100%; border: 0; padding: 0; color: #000; }
  .sheet-letterhead { margin: 0 0 10pt; color: #000; }
  .letter-line { margin: 0; padding: 0; line-height: 1.35; }
  .sheet-kicker {
    text-align: center;
    font-size: 9pt;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #000;
    margin: 0 0 6pt;
  }
  .sheet-title {
    text-align: center;
    font-family: "Times New Roman", Times, serif;
    font-size: 14pt;
    font-weight: bold;
    margin: 6pt 0 4pt;
    color: #000;
  }
  .sheet-sub {
    text-align: center;
    font-style: italic;
    margin: 0 0 2pt;
    color: #000;
  }
  .sheet-meta { margin: 10pt 0 12pt; color: #000; }
  .sheet-h {
    font-size: 12pt;
    margin: 12pt 0 4pt;
    color: #000;
    page-break-after: avoid;
  }
  .sheet-h.center { text-align: center; }
  /* Do not use page-break-inside:avoid in Word — large keeps create blank half-pages. */
  .sheet-p {
    text-align: justify;
    margin: 0 0 6pt;
    color: #000;
    text-indent: 0;
  }
  .sheet-p.preamble { text-indent: 1.25em; margin-bottom: 10pt; }
  .sheet-note { font-size: 10pt; font-style: italic; color: #000; margin: 6pt 0; }
  .sheet-space { margin: 0 0 8pt; }
  table.sheet-kv, table.sheet-table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0 12pt;
  }
  table.sheet-kv th, table.sheet-kv td,
  table.sheet-table th, table.sheet-table td {
    border: 1px solid #000;
    padding: 4pt 5pt;
    vertical-align: top;
    color: #000;
    background: #fff;
    font-size: 10pt;
  }
  table.sheet-table th { font-size: 9pt; }
  table.sheet-invoice-head, table.sheet-meta, table.signs,
  table.sheet-invoice-head td, table.sheet-meta td, table.signs td {
    border: 0 !important;
  }
  .sign-title { margin: 0 0 4pt; }
  .sign-line-text { margin: 0; }
  .sign-gap { margin: 0; line-height: 18pt; }
  .sign-role { margin: 0; font-style: italic; }
  .sign-line { margin: 4pt 0 0; }
  .sign-line-single { margin: 22pt 0 0; }
  .sheet-invoice-title { text-align: center; font-weight: bold; margin: 12pt 0 8pt; }
  .sheet-invoice-buyer { margin: 0 0 10pt; }
  .sheet-invoice-logo { width: 90px; height: auto; }
  /* Page breaks for Word come only from explicit <br page-break-before> markers.
     CSS page-break on .sheet-break / .sheet-annex stacked with those markers and
     produced blank pages between contract, annex, invoice, and act. */
  .sheet-annex { padding-top: 0; margin-top: 0; }
  .sheet-break, .sheet-annex-only { }
</style>
</head>
<body>
<div style="mso-element:header" id="h1"><p class="MsoHeader">&nbsp;</p></div>
<div style="mso-element:footer" id="f1">
  <p class="MsoFooter" style="text-align:center">
    <!--[if supportFields]><span style="mso-element:field-begin"></span> PAGE <span style="mso-element:field-separator"></span><![endif]-->1<!--[if supportFields]><span style="mso-element:field-end"></span><![endif]-->
  </p>
</div>
<div class="WordSection1">
${inner}
</div>
</body>
</html>`;
  const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".doc") ? filename : `${filename}.doc`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
