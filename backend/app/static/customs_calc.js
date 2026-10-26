(function () {
  var root = document.querySelector("[data-customs-calc]");
  if (!root) return;

  var form = root.querySelector("[data-calc-form]");
  var statusEl = root.querySelector("[data-calc-status]");
  var emptyEl = root.querySelector("[data-calc-empty]");
  var bodyEl = root.querySelector("[data-calc-result-body]");
  var totalEl = root.querySelector("[data-calc-total]");
  var vehicleEl = root.querySelector("[data-calc-vehicle]");
  var ageEl = root.querySelector("[data-calc-age]");
  var notesEl = root.querySelector("[data-calc-notes]");
  var utilTag = root.querySelector("[data-calc-util-tag]");
  var makeSelect = root.querySelector("[data-calc-make]");
  var modelSelect = root.querySelector("[data-calc-model]");
  var literSelect = root.querySelector("[data-calc-liter]");
  var ccSelect = root.querySelector("[data-calc-cc]");
  var catalogHp = root.querySelector("[data-calc-catalog-hp]");
  var specMeta = root.querySelector("[data-calc-spec-meta]");
  var mode = root.getAttribute("data-calc-default-mode") === "catalog" ? "catalog" : "manual";

  function money(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return (
      new Intl.NumberFormat("ru-RU", {
        maximumFractionDigits: 0,
      }).format(Math.round(Number(value))) + " ₽"
    );
  }

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.style.color = isError ? "#f87171" : "";
  }

  function setMode(next) {
    mode = next;
    root.querySelectorAll("[data-calc-mode]").forEach(function (btn) {
      var active = btn.getAttribute("data-calc-mode") === next;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    root.querySelectorAll("[data-calc-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-calc-panel") !== next;
    });
  }

  root.querySelectorAll("[data-calc-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setMode(btn.getAttribute("data-calc-mode"));
    });
  });
  setMode(mode);

  function resetSelect(select, placeholder, disabled) {
    if (!select) return;
    select.disabled = !!disabled;
    select.innerHTML = "";
    var opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }

  function litersLabel(value) {
    var n = Number(value);
    return Number.isInteger(n) ? String(n) + " л" : n.toFixed(1) + " л";
  }

  async function loadModels(make) {
    resetSelect(modelSelect, "Загрузка…", true);
    resetSelect(literSelect, "Сначала выберите модель", true);
    resetSelect(ccSelect, "Сначала выберите объём", true);
    if (specMeta) specMeta.textContent = "";
    try {
      var res = await fetch(
        "/api/v1/public/customs-db/models?make=" + encodeURIComponent(make),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить модели");
      resetSelect(modelSelect, rows.length ? "Выберите модель" : "Нет моделей", !rows.length);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = String(row.id);
        opt.textContent = row.name;
        modelSelect.appendChild(opt);
      });
      if (rows.length) modelSelect.disabled = false;
    } catch (err) {
      resetSelect(modelSelect, "Ошибка загрузки", true);
      setStatus(err.message || "Ошибка", true);
    }
  }

  async function loadLiters(modelId) {
    resetSelect(literSelect, "Загрузка…", true);
    resetSelect(ccSelect, "Сначала выберите объём", true);
    if (specMeta) specMeta.textContent = "";
    try {
      var res = await fetch(
        "/api/v1/public/customs-db/liters?model_id=" + encodeURIComponent(modelId),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить объёмы");
      resetSelect(literSelect, rows.length ? "Выберите объём" : "Нет объёмов", !rows.length);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = String(row.id);
        opt.textContent = litersLabel(row.liters);
        literSelect.appendChild(opt);
      });
      if (rows.length) literSelect.disabled = false;
    } catch (err) {
      resetSelect(literSelect, "Ошибка загрузки", true);
      setStatus(err.message || "Ошибка", true);
    }
  }

  async function loadCcs(literId) {
    resetSelect(ccSelect, "Загрузка…", true);
    if (specMeta) specMeta.textContent = "";
    try {
      var res = await fetch(
        "/api/v1/public/customs-db/ccs?liter_id=" + encodeURIComponent(literId),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить см³");
      resetSelect(ccSelect, rows.length ? "Выберите точный объём" : "Нет записей", !rows.length);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = String(row.id);
        opt.textContent = row.engine_cc + " см³";
        opt.dataset.cc = String(row.engine_cc);
        opt.dataset.hp = row.power_hp != null ? String(row.power_hp) : "";
        ccSelect.appendChild(opt);
      });
      if (rows.length) ccSelect.disabled = false;
    } catch (err) {
      resetSelect(ccSelect, "Ошибка загрузки", true);
      setStatus(err.message || "Ошибка", true);
    }
  }

  if (makeSelect) {
    makeSelect.addEventListener("change", function () {
      var make = makeSelect.value;
      if (!make) {
        resetSelect(modelSelect, "Сначала выберите марку", true);
        resetSelect(literSelect, "Сначала выберите модель", true);
        resetSelect(ccSelect, "Сначала выберите объём", true);
        return;
      }
      loadModels(make);
    });
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", function () {
      var id = modelSelect.value;
      if (!id) {
        resetSelect(literSelect, "Сначала выберите модель", true);
        resetSelect(ccSelect, "Сначала выберите объём", true);
        return;
      }
      loadLiters(id);
    });
  }

  if (literSelect) {
    literSelect.addEventListener("change", function () {
      var id = literSelect.value;
      if (!id) {
        resetSelect(ccSelect, "Сначала выберите объём", true);
        return;
      }
      loadCcs(id);
    });
  }

  if (ccSelect) {
    ccSelect.addEventListener("change", function () {
      var opt = ccSelect.selectedOptions[0];
      if (!opt || !opt.value) {
        if (specMeta) specMeta.textContent = "";
        return;
      }
      if (opt.dataset.hp && catalogHp) {
        catalogHp.value = opt.dataset.hp;
      }
      if (specMeta) {
        specMeta.textContent =
          "В расчёт пойдёт " + (opt.dataset.cc || "") + " см³" +
          (opt.dataset.hp ? " · " + opt.dataset.hp + " л.с." : "");
      }
    });
  }

  function renderResult(data) {
    if (!data.ok) {
      emptyEl.hidden = false;
      bodyEl.hidden = true;
      setStatus(data.error || "Не удалось рассчитать", true);
      return;
    }
    setStatus("");
    emptyEl.hidden = true;
    bodyEl.hidden = false;
    totalEl.textContent = money(data.total_rub);
    ["customs_value_rub", "duty_rub", "clearance_fee_rub", "util_sbor_rub"].forEach(
      function (key) {
        var el = root.querySelector('[data-calc-line="' + key + '"]');
        if (el) el.textContent = money(data[key]);
      }
    );
    if (utilTag) {
      utilTag.textContent = data.util_preferential
        ? "(льготный ×" + data.util_coefficient + ")"
        : "(×" + data.util_coefficient + ")";
    }
    if (vehicleEl) {
      if (data.vehicle_label) {
        vehicleEl.hidden = false;
        vehicleEl.textContent = data.vehicle_label;
      } else {
        vehicleEl.hidden = true;
        vehicleEl.textContent = "";
      }
    }
    if (ageEl) {
      ageEl.textContent =
        "Возраст: " + (data.age_band_label || data.age_band || "—") + ".";
    }
    if (notesEl) {
      notesEl.innerHTML = "";
      (data.notes || []).forEach(function (note) {
        var li = document.createElement("li");
        li.textContent = note;
        notesEl.appendChild(li);
      });
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    setStatus("Считаем…");
    var fd = new FormData(form);
    var payload = {
      price: Number(fd.get("price")),
      currency: String(fd.get("currency") || "EUR"),
      importer: String(fd.get("importer") || "personal"),
      engine_kind: "ice",
      age_band: "from3to5",
      engine_cc: 0,
      power_hp: 0,
      engine_cc_id: null,
      vehicle_spec_id: null,
    };

    if (mode === "catalog") {
      var ccId = Number(fd.get("engine_cc_id") || 0);
      if (!ccId) {
        setStatus("Выберите марку, модель, объём и точные см³", true);
        return;
      }
      payload.engine_cc_id = ccId;
      payload.age_band = String(fd.get("catalog_age_band") || "from3to5");
      payload.power_hp = Number(fd.get("catalog_power_hp") || 0);
      var opt = ccSelect && ccSelect.selectedOptions[0];
      if (opt) {
        payload.engine_cc = Number(opt.dataset.cc || 0);
        if (opt.dataset.hp) payload.power_hp = Number(opt.dataset.hp);
      }
    } else {
      payload.age_band = String(fd.get("age_band") || "from3to5");
      payload.engine_cc = Number(fd.get("engine_cc"));
      payload.power_hp = Number(fd.get("power_hp"));
      payload.engine_kind = String(fd.get("engine_kind") || "ice");
    }

    try {
      var res = await fetch("/api/v1/public/customs-calc", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      var data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Ошибка расчёта"
        );
      }
      renderResult(data);
    } catch (err) {
      setStatus(err.message || "Ошибка", true);
    }
  });
})();
