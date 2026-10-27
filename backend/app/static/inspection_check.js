(function () {
  var root = document.querySelector("[data-inspection-page]");
  if (!root) return;

  var form = root.querySelector("[data-inspection-form]");
  var statusEl = root.querySelector("[data-inspection-status]");
  var resultEl = root.querySelector("[data-inspection-result]");
  var promo = root.querySelector("[data-inspection-promo]");
  var promoTitle = root.querySelector("[data-promo-title]");
  var promoText = root.querySelector("[data-promo-text]");
  var promoActions = root.querySelector("[data-promo-actions]");
  if (!form || !resultEl) return;

  var DEFAULT_PROMO = {
    mode: "select",
    title: "Подберём авто под льготный утильсбор",
    text:
      "Подбор в Беларуси и Европе: поиск, проверка истории, расчёт утильсбора и доставка в Москву и регионы.",
    actionsHtml:
      '<a class="home-hero-pane-cta" href="/listings">Авто из Беларуси</a>' +
      '<a class="home-hero-pane-cta home-hero-pane-cta--ghost" href="/listings/eu">Авто из Европы</a>',
  };

  var INSPECT_PROMO = {
    mode: "inspect",
    title: "Закажите проверку этого авто у Auto160",
    text:
      "Осмотр, история и риски перед покупкой — поможем принять решение по конкретной машине.",
    actionsHtml:
      '<a class="home-hero-pane-cta" href="/listings">Заказать проверку</a>' +
      '<a class="home-hero-pane-cta home-hero-pane-cta--ghost" href="/#chat" data-open-chat>Написать менеджеру</a>',
  };

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

  function paramMark(ok) {
    if (ok === true) {
      return '<span class="inspection-param-mark is-ok" aria-label="Подходит" title="Подходит">✓</span>';
    }
    if (ok === false) {
      return '<span class="inspection-param-mark is-bad" aria-label="Не подходит" title="Не подходит">✕</span>';
    }
    return '<span class="inspection-param-mark is-na" aria-hidden="true"></span>';
  }

  function paramRow(ok, label, valueHtml) {
    return (
      '<p class="inspection-param-row">' +
      paramMark(ok) +
      "<span><strong>" +
      escapeHtml(label) +
      ":</strong> " +
      valueHtml +
      "</span></p>"
    );
  }

  function setPromo(config) {
    if (!promo || !promoTitle || !promoText || !promoActions) return;
    promo.setAttribute("data-promo-mode", config.mode);
    promoTitle.textContent = config.title;
    promoText.textContent = config.text;
    promoActions.innerHTML = config.actionsHtml;
  }

  function applyPromoForCta(cta) {
    if (cta === "inspect") {
      setPromo(INSPECT_PROMO);
      return;
    }
    setPromo(DEFAULT_PROMO);
  }

  function renderResult(data) {
    resultEl.hidden = false;
    if (!data.ok) {
      applyPromoForCta("select");
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
    var checks = verdict.checks || {};
    var bits = [];

    if (data.brand || data.model) {
      bits.push(
        "<p><strong>Авто:</strong> " +
          escapeHtml([data.brand, data.model, data.year].filter(Boolean).join(" ")) +
          "</p>"
      );
    }
    if (data.release_date) {
      bits.push(
        paramRow(
          checks.import_date,
          "Дата ввоза в РБ",
          escapeHtml(data.release_date)
        )
      );
    }
    if (data.input_kind === "avby_url") {
      if (data.power_hp != null) {
        bits.push(
          paramRow(checks.power, "Мощность", escapeHtml(String(data.power_hp)) + " л.с.")
        );
      }
      if (data.engine_cc != null) {
        bits.push(
          paramRow(checks.volume, "Объём", escapeHtml(String(data.engine_cc)) + " см³")
        );
      } else if (data.engine_capacity_l != null) {
        bits.push(
          paramRow(
            checks.volume,
            "Объём",
            escapeHtml(String(data.engine_capacity_l)) + " л"
          )
        );
      }
    }
    if (data.vin) {
      bits.push("<p><strong>VIN:</strong> <code>" + escapeHtml(data.vin) + "</code></p>");
    }
    if (data.message && !verdict.title) {
      bits.push("<p>" + escapeHtml(data.message) + "</p>");
    }

    applyPromoForCta(verdict.cta);

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
