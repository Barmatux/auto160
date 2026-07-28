(function () {
  function initVehicleHierarchyFilters(root, config) {
    if (!root || root.dataset.vhInit === "1") return;
    root.dataset.vhInit = "1";

    const makeField = root.dataset.makeField || "make";
    const modelField = root.dataset.modelField || "model";
    const generationField = root.dataset.generationField || "generation";
    const formId = root.dataset.formId || "";
    const rowsContainer = root.querySelector(".vehicle-hierarchy-rows");
    const addButton = root.querySelector(".vehicle-hierarchy-add");

    const labels = { make: "Марка", model: "Модель", generation: "Поколение" };
    const modelMap = config.modelMap || {};
    const generationMap = config.generationMap || {};
    const makes = (config.makes || []).slice().sort((a, b) => a.localeCompare(b, "ru"));

    function rowValues(row) {
      return {
        make: row.querySelector('[data-tier="make"]')?.value || "",
        model: row.querySelector('[data-tier="model"]')?.value || "",
        generation: row.querySelector('[data-tier="generation"]')?.value || "",
      };
    }

    function fillSelect(select, options, placeholder, selected) {
      select.innerHTML = "";
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = placeholder;
      select.appendChild(empty);
      options.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === selected) option.selected = true;
        select.appendChild(option);
      });
    }

    function syncRowSelects(row, values) {
      const makeSelect = row.querySelector('[data-tier="make"]');
      const modelSelect = row.querySelector('[data-tier="model"]');
      const generationSelect = row.querySelector('[data-tier="generation"]');

      fillSelect(makeSelect, makes, labels.make, values.make);

      const models = values.make ? (modelMap[values.make] || []).slice() : [];
      fillSelect(modelSelect, models, labels.model, values.model);
      modelSelect.disabled = !values.make;

      const generations =
        values.make && values.model
          ? (generationMap[values.make]?.[values.model] || []).slice()
          : [];
      fillSelect(generationSelect, generations, labels.generation, values.generation);
      generationSelect.disabled = !values.model;
    }

    function formAttr() {
      return formId ? ' form="' + formId + '"' : "";
    }

    function createRow(values) {
      values = values || { make: "", model: "", generation: "" };
      const row = document.createElement("div");
      row.className = "vehicle-hierarchy-row";
      row.innerHTML =
        '<label class="vehicle-hierarchy-field">' +
        '<span class="vehicle-hierarchy-label">' +
        labels.make +
        "</span>" +
        '<select name="' +
        makeField +
        '" data-tier="make"' +
        formAttr() +
        "></select>" +
        "</label>" +
        '<label class="vehicle-hierarchy-field">' +
        '<span class="vehicle-hierarchy-label">' +
        labels.model +
        "</span>" +
        '<select name="' +
        modelField +
        '" data-tier="model"' +
        formAttr() +
        "></select>" +
        "</label>" +
        '<label class="vehicle-hierarchy-field">' +
        '<span class="vehicle-hierarchy-label">' +
        labels.generation +
        "</span>" +
        '<select name="' +
        generationField +
        '" data-tier="generation"' +
        formAttr() +
        "></select>" +
        "</label>" +
        '<button type="button" class="vehicle-hierarchy-remove" aria-label="Удалить строку">×</button>';

      syncRowSelects(row, values);
      bindRow(row);
      return row;
    }

    function bindRow(row) {
      const makeSelect = row.querySelector('[data-tier="make"]');
      const modelSelect = row.querySelector('[data-tier="model"]');
      const generationSelect = row.querySelector('[data-tier="generation"]');
      const removeButton = row.querySelector(".vehicle-hierarchy-remove");

      makeSelect.addEventListener("change", () => {
        syncRowSelects(row, { make: makeSelect.value, model: "", generation: "" });
      });

      modelSelect.addEventListener("change", () => {
        syncRowSelects(row, {
          make: makeSelect.value,
          model: modelSelect.value,
          generation: "",
        });
      });

      removeButton.addEventListener("click", () => {
        const rows = rowsContainer.querySelectorAll(".vehicle-hierarchy-row");
        if (rows.length <= 1) {
          syncRowSelects(row, { make: "", model: "", generation: "" });
          return;
        }
        row.remove();
      });
    }

    rowsContainer.querySelectorAll(".vehicle-hierarchy-row").forEach((row) => {
      bindRow(row);
      syncRowSelects(row, rowValues(row));
    });

    addButton.addEventListener("click", () => {
      rowsContainer.appendChild(createRow());
    });

    const form = formId ? document.getElementById(formId) : root.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        rowsContainer.querySelectorAll(".vehicle-hierarchy-row").forEach((row) => {
          const values = rowValues(row);
          if (!values.make && !values.model && !values.generation) {
            row.remove();
          }
        });
      });
    }
  }

  window.initVehicleHierarchyFilters = initVehicleHierarchyFilters;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-vehicle-hierarchy-config]").forEach((root) => {
      try {
        const config = JSON.parse(root.getAttribute("data-vehicle-hierarchy-config") || "{}");
        initVehicleHierarchyFilters(root, config);
      } catch (err) {
        console.error("vehicle hierarchy filters init failed", err);
      }
    });
  });
})();
