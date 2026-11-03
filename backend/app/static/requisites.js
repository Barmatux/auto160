(function () {
  var root = document.querySelector("[data-requisites-page]");
  if (!root) return;

  function flashCopied(btn) {
    if (!btn) return;
    btn.classList.add("is-copied");
    var prev = btn.getAttribute("aria-label") || "";
    btn.setAttribute("aria-label", "Скопировано");
    window.clearTimeout(btn._copyTimer);
    btn._copyTimer = window.setTimeout(function () {
      btn.classList.remove("is-copied");
      if (prev) btn.setAttribute("aria-label", prev);
    }, 1400);
  }

  function copyText(text, btn) {
    var value = String(text || "").trim();
    if (!value) return;
    var done = function () {
      flashCopied(btn);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(done).catch(function () {
        fallbackCopy(value, done);
      });
      return;
    }
    fallbackCopy(value, done);
  }

  function fallbackCopy(value, done) {
    var ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      done();
    } catch (err) {
      /* ignore */
    }
    document.body.removeChild(ta);
  }

  root.querySelectorAll("[data-copy-btn]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      copyText(btn.getAttribute("data-copy-text"), btn);
    });
  });

  var bank = root.querySelector("[data-requisites-bank]");
  if (!bank) return;

  var toggle = bank.querySelector("[data-requisites-bank-toggle]");
  var panel = bank.querySelector("[data-requisites-bank-panel]");
  var copyAll = bank.querySelector("[data-copy-bank-all]");
  var payloadEl = bank.querySelector("[data-bank-copy-payload]");

  function setOpen(open) {
    if (!toggle || !panel) return;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    bank.classList.toggle("is-open", open);
    panel.hidden = !open;
    if (copyAll) copyAll.hidden = !open;
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
  }

  if (copyAll && payloadEl) {
    copyAll.addEventListener("click", function () {
      var lines = [
        payloadEl.getAttribute("data-company") || "",
        payloadEl.getAttribute("data-unp") ? "УНП " + payloadEl.getAttribute("data-unp") : "",
        payloadEl.getAttribute("data-account")
          ? "Расчётный счёт в белорусских рублях: " + payloadEl.getAttribute("data-account")
          : "",
        payloadEl.getAttribute("data-bank") ? "Банк: " + payloadEl.getAttribute("data-bank") : "",
        payloadEl.getAttribute("data-bank-address")
          ? "Адрес банка: " + payloadEl.getAttribute("data-bank-address")
          : "",
        payloadEl.getAttribute("data-swift") ? "SWIFT: " + payloadEl.getAttribute("data-swift") : "",
        payloadEl.getAttribute("data-bank-unp")
          ? "УНП банка: " + payloadEl.getAttribute("data-bank-unp")
          : "",
        payloadEl.getAttribute("data-bank-okpo")
          ? "ОКПО банка: " + payloadEl.getAttribute("data-bank-okpo")
          : "",
      ].filter(Boolean);
      copyText(lines.join("\n"), copyAll);
    });
  }
})();
