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
  var queryInput = root.querySelector("[data-inspection-query]");
  var clearBtn = root.querySelector("[data-inspection-clear]");
  if (!form || !resultEl) return;

  function syncClearButton() {
    if (!clearBtn || !queryInput) return;
    clearBtn.hidden = !String(queryInput.value || "").trim();
  }

  if (queryInput && clearBtn) {
    syncClearButton();
    queryInput.addEventListener("input", syncClearButton);
    queryInput.addEventListener("change", syncClearButton);
    clearBtn.addEventListener("click", function () {
      queryInput.value = "";
      syncClearButton();
      resultEl.hidden = true;
      resultEl.innerHTML = "";
      if (statusEl) {
        statusEl.hidden = true;
        statusEl.textContent = "";
      }
      if (window.history && window.history.replaceState) {
        window.history.replaceState({}, "", "/inspection");
      }
      queryInput.focus();
    });
  }

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

  var toastEl = root.querySelector("[data-inspection-toast]");
  var toastTimer = null;
  var messengers = [];
  try {
    messengers = JSON.parse(root.getAttribute("data-messengers") || "[]") || [];
  } catch (_err) {
    messengers = [];
  }

  function applyPromoForCta(cta) {
    if (cta === "inspect" || cta === "notify") {
      setPromo(INSPECT_PROMO);
      return;
    }
    setPromo(DEFAULT_PROMO);
  }

  function showToast(text) {
    if (!toastEl) return;
    toastEl.hidden = false;
    toastEl.textContent = text;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.hidden = true;
      toastEl.textContent = "";
    }, 2000);
  }

  function buildShareUrl(data) {
    var origin = window.location.origin;
    if (!data) return origin + "/inspection";
    if (data.input_kind === "vin") {
      var vin = String(data.vin || (queryInput && queryInput.value) || "")
        .trim()
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "");
      if (vin.length === 17) {
        return origin + "/inspection?vin=" + encodeURIComponent(vin);
      }
    }
    // Prefer the public av.by URL so the shared page can re-run for any visitor.
    if (data.avby_url) {
      return origin + "/inspection?q=" + encodeURIComponent(String(data.avby_url));
    }
    var raw = String(data.query || (queryInput && queryInput.value) || "").trim();
    if (!raw) return origin + "/inspection";
    return origin + "/inspection?q=" + encodeURIComponent(raw);
  }

  function syncShareUrl(data) {
    if (!window.history || !window.history.replaceState) return;
    var url = buildShareUrl(data);
    var nextPath = url.replace(window.location.origin, "");
    var currentPath = window.location.pathname + window.location.search;
    if (nextPath !== currentPath) {
      window.history.replaceState({ inspectionShare: true }, "", nextPath);
    }
  }

  function copyText(text, okMessage) {
    var done = function () {
      showToast(okMessage || "Ссылка скопирована в буфер обмена");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () {
        window.prompt("Скопируйте ссылку:", text);
      });
    } else {
      window.prompt("Скопируйте ссылку:", text);
    }
  }

  function renderShareBlock(data) {
    var shareUrl = buildShareUrl(data);
    return (
      '<div class="inspection-share">' +
      "<p><strong>Ссылка на эту проверку</strong> — можно отправить другу:</p>" +
      '<div class="inspection-retry-row">' +
      '<a class="inspection-retry-link" href="' +
      escapeHtml(shareUrl) +
      '">' +
      escapeHtml(shareUrl) +
      "</a>" +
      '<button type="button" class="inspection-copy-btn" data-copy-share aria-label="Скопировать ссылку" title="Скопировать">' +
      '<span aria-hidden="true">⧉</span>' +
      "</button></div></div>"
    );
  }

  function renderReasons(reasons) {
    if (!reasons || !reasons.length) return "";
    return (
      '<div class="inspection-reasons">' +
      "<p><strong>Возможные причины:</strong></p>" +
      "<ul>" +
      reasons
        .map(function (item) {
          return "<li>" + escapeHtml(item) + "</li>";
        })
        .join("") +
      "</ul></div>"
    );
  }

  function renderNotifyBlock(data) {
    var messengerHtml = messengers
      .map(function (item) {
        return (
          '<a class="inspection-messenger-link" href="' +
          escapeHtml(item.url) +
          '" target="_blank" rel="noopener noreferrer">' +
          escapeHtml(item.label) +
          "</a>"
        );
      })
      .join("");
    return (
      '<div class="inspection-notify">' +
      "<p>Зайдите позже по ссылке выше или пришлите её нам — сообщим результат, когда ГТК ответит.</p>" +
      (messengerHtml
        ? '<div class="inspection-messenger-row">' + messengerHtml + "</div>"
        : "") +
      '<form class="inspection-notify-form" data-inspection-notify-form>' +
      "<label>Email или контакт в мессенджере" +
      '<input type="text" name="contact" maxlength="200" placeholder="email@example.com или @username" required />' +
      "</label>" +
      '<input type="hidden" name="avby_url" value="' +
      escapeHtml(data.avby_url || data.query || "") +
      '" />' +
      '<input type="hidden" name="listing_id" value="' +
      escapeHtml(data.listing_id != null ? String(data.listing_id) : "") +
      '" />' +
      '<div class="actions-row"><button type="submit" class="btn-primary">Прислать результат</button></div>' +
      '<p class="hint" data-notify-status hidden></p>' +
      "</form></div>"
    );
  }

  function bindResultActions(data) {
    var copyBtns = resultEl.querySelectorAll("[data-copy-share]");
    Array.prototype.forEach.call(copyBtns, function (btn) {
      btn.addEventListener("click", function () {
        copyText(buildShareUrl(data), "Ссылка скопирована в буфер обмена");
      });
    });

    var notifyForm = resultEl.querySelector("[data-inspection-notify-form]");
    if (!notifyForm) return;
    var notifyStatus = notifyForm.querySelector("[data-notify-status]");
    notifyForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var fd = new FormData(notifyForm);
      var contact = String(fd.get("contact") || "").trim();
      if (!contact) return;
      if (notifyStatus) {
        notifyStatus.hidden = false;
        notifyStatus.textContent = "Отправляем…";
        notifyStatus.style.color = "";
      }
      try {
        var res = await fetch("/api/v1/public/leads", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contact_name: "Проверка ГТК",
            contact: contact,
            comment: "Нужен результат проверки: " + buildShareUrl(data),
            listing_id: data.listing_id || null,
            avby_url: data.avby_url || null,
            source: "inspection_customs_retry",
          }),
        });
        var payload = await res.json().catch(function () {
          return {};
        });
        if (!res.ok) {
          throw new Error(
            typeof payload.detail === "string" ? payload.detail : "Не удалось отправить"
          );
        }
        if (notifyStatus) {
          notifyStatus.textContent = "Приняли — напишем, когда появится ответ ГТК.";
        }
        notifyForm.querySelector('button[type="submit"]').disabled = true;
      } catch (err) {
        if (notifyStatus) {
          notifyStatus.textContent = err.message || "Ошибка отправки";
          notifyStatus.style.color = "#f87171";
        }
      }
    });
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
        var ccPrefix = data.engine_cc_approximate
          ? '<span class="inspection-approx" title="Приблизительно (литры × 1000)">≈</span> '
          : "";
        bits.push(
          paramRow(
            checks.volume,
            "Объём",
            ccPrefix + escapeHtml(String(data.engine_cc)) + " см³"
          )
        );
      } else if (data.engine_capacity_l != null) {
        bits.push(
          paramRow(
            checks.volume,
            "Объём",
            '<span class="inspection-approx" title="Приблизительно">≈</span> ' +
              escapeHtml(String(data.engine_capacity_l)) +
              " л"
          )
        );
      }
    }
    if (data.vin) {
      bits.push("<p><strong>VIN:</strong> <code>" + escapeHtml(data.vin) + "</code></p>");
    }
    if (verdict.detail) {
      bits.push('<p class="inspection-verdict-detail">' + escapeHtml(verdict.detail) + "</p>");
    }
    if (verdict.code === "not_found") {
      bits.push(renderReasons(verdict.reasons));
    }
    bits.push(renderShareBlock(data));
    if (verdict.code === "customs_unavailable" || data.customs_status === "unavailable") {
      bits.push(renderNotifyBlock(data));
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

    syncShareUrl(data);
    bindResultActions(data);

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
