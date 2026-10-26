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
  var specSelect = root.querySelector("[data-calc-spec]");
  var specMeta = root.querySelector("[data-calc-spec-meta]");
  var mode = "manual";

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
      var show = panel.getAttribute("data-calc-panel") === next;
      panel.hidden = !show;
    });
  }

  root.querySelectorAll("[data-calc-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setMode(btn.getAttribute("data-calc-mode"));
    });
  });

  async function loadSpecs(make) {
    if (!specSelect) return;
    specSelect.disabled = true;
    specSelect.innerHTML = "<option value=\"\">Загрузка…</option>";
    if (specMeta) specMeta.textContent = "";
    try {
      var res = await fetch(
        "/api/v1/public/customs-vehicles?make=" + encodeURIComponent(make),
        { credentials: "same-origin" }
      );
      var rows = await res.json();
      if (!res.ok) throw new Error("Не удалось загрузить комплектации");
      specSelect.innerHTML = "";
      if (!rows.length) {
        specSelect.innerHTML = "<option value=\"\">Нет комплектаций</option>";
        return;
      }
      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Выберите комплектацию";
      specSelect.appendChild(placeholder);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = String(row.id);
        var label = row.model;
        if (row.generation) label += " · " + row.generation;
        label += " · " + row.engine_cc + " см³ · " + row.power_hp + " л.с.";
        opt.textContent = label;
        opt.dataset.cc = String(row.engine_cc);
        opt.dataset.hp = String(row.power_hp);
        opt.dataset.kind = row.engine_kind || "ice";
        opt.dataset.yearFrom = row.year_from != null ? String(row.year_from) : "";
        opt.dataset.yearTo = row.year_to != null ? String(row.year_to) : "";
        opt.dataset.notes = row.notes || "";
        specSelect.appendChild(opt);
      });
      specSelect.disabled = false;
    } catch (err) {
      specSelect.innerHTML = "<option value=\"\">Ошибка загрузки</option>";
      setStatus(err.message || "Ошибка", true);
    }
  }

  if (makeSelect) {
    makeSelect.addEventListener("change", function () {
      var make = makeSelect.value;
      if (!make) {
        if (specSelect) {
          specSelect.disabled = true;
          specSelect.innerHTML = "<option value=\"\">Сначала выберите марку</option>";
        }
        if (specMeta) specMeta.textContent = "";
        return;
      }
      loadSpecs(make);
    });
  }

  if (specSelect) {
    specSelect.addEventListener("change", function () {
      var opt = specSelect.selectedOptions[0];
      if (!opt || !opt.value) {
        if (specMeta) specMeta.textContent = "";
        return;
      }
      var yearInput = form.querySelector('[name="catalog_year"]');
      if (yearInput && !yearInput.value) {
        yearInput.value = opt.dataset.yearTo || opt.dataset.yearFrom || "";
      } else if (yearInput && (opt.dataset.yearTo || opt.dataset.yearFrom)) {
        var y = Number(yearInput.value);
        var from = opt.dataset.yearFrom ? Number(opt.dataset.yearFrom) : null;
        var to = opt.dataset.yearTo ? Number(opt.dataset.yearTo) : null;
        if ((from && y < from) || (to && y > to)) {
          yearInput.value = String(to || from);
        }
      }
      if (specMeta) {
        var bits = [];
        if (opt.dataset.cc) bits.push(opt.dataset.cc + " см³");
        if (opt.dataset.hp) bits.push(opt.dataset.hp + " л.с.");
        if (opt.dataset.notes) bits.push(opt.dataset.notes);
        specMeta.textContent = bits.join(" · ");
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
      var band =
        data.age_band === "under3"
          ? "младше 3 лет"
          : data.age_band === "from3to5"
            ? "от 3 до 5 лет"
            : "старше 5 лет";
      ageEl.textContent =
        "Возраст ≈ " + data.age_years + " лет (" + band + ").";
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
      year: 0,
      engine_cc: 0,
      power_hp: 0,
      vehicle_spec_id: null,
    };

    if (mode === "catalog") {
      var specId = Number(fd.get("vehicle_spec_id") || 0);
      if (!specId) {
        setStatus("Выберите марку и комплектацию", true);
        return;
      }
      payload.vehicle_spec_id = specId;
      payload.year = Number(fd.get("catalog_year") || 0);
      payload.power_hp = 1;
      var opt = specSelect && specSelect.selectedOptions[0];
      if (opt) {
        payload.engine_kind = opt.dataset.kind || "ice";
        payload.engine_cc = Number(opt.dataset.cc || 0);
        payload.power_hp = Number(opt.dataset.hp || 1);
      }
    } else {
      payload.year = Number(fd.get("year"));
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
