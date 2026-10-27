(function () {
  var root = document.querySelector("[data-inspection-page]");
  if (!root) return;

  var form = root.querySelector("[data-inspection-form]");
  var statusEl = root.querySelector("[data-inspection-status]");
  var resultEl = root.querySelector("[data-inspection-result]");
  if (!form || !resultEl) return;

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.style.color = isError ? "#f87171" : "";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toneIcon(tone) {
    if (tone === "green") return "✓";
    if (tone === "yellow") return "!";
    if (tone === "red") return "✕";
    return "i";
  }

  function renderCta(cta) {
    if (cta === "inspect") {
      return (
        '<div class="inspection-cta">' +
        "<p>Можем проверить этот автомобиль для вас — осмотр, история, риски перед покупкой.</p>" +
        '<div class="inspection-cta-actions">' +
        '<a class="btn-primary" href="/listings">Заказать проверку у Auto160</a>' +
        '<a class="btn-secondary" href="/#chat" data-open-chat>Написать менеджеру</a>' +
        "</div></div>"
      );
    }
    if (cta === "select") {
      return (
        '<div class="inspection-cta">' +
        "<p>Подберём автомобиль под льготный утильсбор в Беларуси или Европе.</p>" +
        '<div class="inspection-cta-actions">' +
        '<a class="btn-primary" href="/listings">Авто из Беларуси</a>' +
        '<a class="btn-secondary" href="/listings/eu">Авто из Европы</a>' +
        "</div></div>"
      );
    }
    return "";
  }

  function renderResult(data) {
    resultEl.hidden = false;
    if (!data.ok) {
      resultEl.innerHTML =
        '<div class="inspection-verdict-card is-neutral">' +
        '<div class="inspection-verdict-mark" aria-hidden="true">i</div>' +
        '<div class="inspection-verdict-body">' +
        "<h3>Не удалось проверить</h3>" +
        "<p>" +
        escapeHtml(data.message || "Ошибка запроса") +
        "</p></div></div>";
      return;
    }

    var verdict = data.verdict || {};
    var tone = verdict.tone || "neutral";
    var bits = [];
    if (data.release_date) {
      bits.push("<p><strong>Дата ввоза в РБ:</strong> " + escapeHtml(data.release_date) + "</p>");
    }
    if (data.brand || data.model) {
      bits.push(
        "<p><strong>Авто:</strong> " +
          escapeHtml([data.brand, data.model, data.year].filter(Boolean).join(" ")) +
          "</p>"
      );
    }
    if (data.input_kind === "avby_url") {
      if (data.power_hp != null) {
        bits.push("<p><strong>Мощность:</strong> " + escapeHtml(String(data.power_hp)) + " л.с.</p>");
      }
      if (data.engine_cc != null) {
        bits.push("<p><strong>Объём:</strong> " + escapeHtml(String(data.engine_cc)) + " см³</p>");
      } else if (data.engine_capacity_l != null) {
        bits.push(
          "<p><strong>Объём:</strong> " + escapeHtml(String(data.engine_capacity_l)) + " л</p>"
        );
      }
    }
    if (data.vin) {
      bits.push("<p><strong>VIN:</strong> <code>" + escapeHtml(data.vin) + "</code></p>");
    }
    if (verdict.detail) {
      bits.push("<p class=\"inspection-verdict-detail\">" + escapeHtml(verdict.detail) + "</p>");
    }
    if (data.message && !verdict.title) {
      bits.push("<p>" + escapeHtml(data.message) + "</p>");
    }

    resultEl.innerHTML =
      '<div class="inspection-verdict-card is-' +
      escapeHtml(tone) +
      '">' +
      '<div class="inspection-verdict-mark" aria-hidden="true">' +
      toneIcon(tone) +
      "</div>" +
      '<div class="inspection-verdict-body">' +
      "<h3>" +
      escapeHtml(verdict.title || "Результат проверки") +
      "</h3>" +
      bits.join("") +
      renderCta(verdict.cta) +
      "</div></div>";

    if (typeof reachMetrikaGoal === "function") {
      reachMetrikaGoal("inspection_check");
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var fd = new FormData(form);
    var query = String(fd.get("query") || "").trim();
    if (!query) {
      setStatus("Введите VIN или ссылку av.by", true);
      return;
    }
    setStatus("Проверяем…");
    resultEl.hidden = true;
    resultEl.innerHTML = "";
    try {
      var res = await fetch("/api/v1/public/inspection-check", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query }),
      });
      var data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Ошибка проверки");
      }
      setStatus("");
      renderResult(data);
    } catch (err) {
      setStatus(err.message || "Ошибка", true);
    }
  });

  // Auto-run if query prefilled (e.g. listing_id flow left a query in the field).
  var initial = form.querySelector('input[name="query"]');
  if (initial && initial.value && initial.value.trim().length >= 10) {
    form.requestSubmit();
  }
})();
