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
  var motorSelect = root.querySelector("[data-calc-motor]");
  var volumeInput = root.querySelector("[data-calc-volume]");
  var catalogHp = root.querySelector("[data-calc-catalog-hp]");
  var specMeta = root.querySelector("[data-calc-spec-meta]");

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

  function resetSelect(select, placeholder, disabled) {
    if (!select) return;
    select.disabled = !!disabled;
    select.innerHTML = "";
    var opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }

  function clearMotorFields() {
    if (volumeInput) volumeInput.value = "";
    if (catalogHp) catalogHp.value = "";
    if (specMeta) specMeta.textContent = "";
  }

  async function loadMakes() {
    if (!makeSelect) return;
    try {
      var res = await fetch("/api/v1/public/customs-catalog/makes", {
        credentials: "same-origin",
      });
      var rows = await res.json();
      if (!res.ok || !Array.isArray(rows)) return;
      var current = makeSelect.value;
      resetSelect(makeSelect, rows.length ? "Выберите марку" : "Нет марок в каталоге", !rows.length);
      rows.forEach(function (name) {
        var opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        makeSelect.appendChild(opt);
      });
      if (current && rows.indexOf(current) >= 0) {
        makeSelect.value = current;
      }
      if (rows.length) makeSelect.disabled = false;
    } catch (_err) {
      /* keep SSR options */
    }
  }

  async function loadModels(make) {
    resetSelect(modelSelect, "Загрузка…", true);
    resetSelect(motorSelect, "Сначала выберите модель", true);
    clearMotorFields();
    try {
      var res = await fetch(
        "/api/v1/public/customs-catalog/models?make=" + encodeURIComponent(make),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить модели");
      resetSelect(modelSelect, rows.length ? "Выберите модель" : "Нет моделей", !rows.length);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = row.name;
        opt.textContent = row.name;
        modelSelect.appendChild(opt);
      });
      if (rows.length) modelSelect.disabled = false;
    } catch (err) {
      resetSelect(modelSelect, "Ошибка загрузки", true);
      setStatus(err.message || "Ошибка", true);
    }
  }

  async function loadMotors(make, model) {
    resetSelect(motorSelect, "Загрузка…", true);
    clearMotorFields();
    try {
      var res = await fetch(
        "/api/v1/public/customs-catalog/motors?make=" +
          encodeURIComponent(make) +
          "&model=" +
          encodeURIComponent(model),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить моторы");
      resetSelect(
        motorSelect,
        rows.length ? "Выберите мотор / конфигурацию" : "Нет конфигураций в каталоге",
        !rows.length
      );
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = String(row.id);
        opt.textContent = row.label;
        opt.dataset.cc = String(row.engine_cc || 0);
        opt.dataset.hp = row.power_hp != null ? String(row.power_hp) : "";
        opt.dataset.kind = row.engine_kind || "ice";
        opt.dataset.label = row.label || "";
        motorSelect.appendChild(opt);
      });
      if (rows.length) motorSelect.disabled = false;
    } catch (err) {
      resetSelect(motorSelect, "Ошибка загрузки", true);
      setStatus(err.message || "Ошибка", true);
    }
  }

  function applyMotorSelection() {
    var opt = motorSelect && motorSelect.selectedOptions[0];
    if (!opt || !opt.value) {
      clearMotorFields();
      return;
    }
    if (volumeInput) {
      volumeInput.value =
        opt.dataset.kind === "electric" ? "электро" : opt.dataset.cc || "";
    }
    if (catalogHp) catalogHp.value = opt.dataset.hp || "";
    if (specMeta) {
      var bits = [];
      if (opt.dataset.kind === "electric") bits.push("электро");
      else if (opt.dataset.cc) bits.push(opt.dataset.cc + " см³");
      if (opt.dataset.hp) bits.push(opt.dataset.hp + " л.с.");
      specMeta.textContent = bits.length
        ? "В расчёт пойдёт " + bits.join(" · ")
        : "";
    }
  }

  if (makeSelect) {
    makeSelect.addEventListener("change", function () {
      var make = makeSelect.value;
      if (!make) {
        resetSelect(modelSelect, "Сначала выберите марку", true);
        resetSelect(motorSelect, "Сначала выберите модель", true);
        clearMotorFields();
        return;
      }
      loadModels(make);
    });
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", function () {
      var model = modelSelect.value;
      var make = makeSelect ? makeSelect.value : "";
      if (!model || !make) {
        resetSelect(motorSelect, "Сначала выберите модель", true);
        clearMotorFields();
        return;
      }
      loadMotors(make, model);
    });
  }

  if (motorSelect) {
    motorSelect.addEventListener("change", applyMotorSelection);
  }

  loadMakes();

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
    var itemId = Number(fd.get("catalog_item_id") || 0);
    if (!itemId) {
      setStatus("Выберите марку, модель и мотор из каталога", true);
      return;
    }
    var opt = motorSelect && motorSelect.selectedOptions[0];
    var payload = {
      price: Number(fd.get("price")),
      currency: String(fd.get("currency") || "EUR"),
      importer: String(fd.get("importer") || "personal"),
      engine_kind: (opt && opt.dataset.kind) || "ice",
      age_band: String(fd.get("catalog_age_band") || "from3to5"),
      engine_cc: opt ? Number(opt.dataset.cc || 0) : 0,
      power_hp: opt && opt.dataset.hp ? Number(opt.dataset.hp) : 0,
      catalog_item_id: itemId,
      engine_cc_id: null,
      vehicle_spec_id: null,
    };

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
      setStatus(err.message || "Ошибка расчёта", true);
    }
  });
})();
