(function () {
  function initVehicleHierarchyFilters(root, config) {
    if (!root || root.dataset.vhInit === "1") return;
    root.dataset.vhInit = "1";

    const makeInput = root.querySelector('[data-tier-input="make"]');
    const modelInput = root.querySelector('[data-tier-input="model"]');
    const generationInput = root.querySelector('[data-tier-input="generation"]');
    const makeChip = root.querySelector('[data-tier-chip="make"]');
    const modelChip = root.querySelector('[data-tier-chip="model"]');
    const generationChip = root.querySelector('[data-tier-chip="generation"]');
    const panel = root.querySelector(".vehicle-filter-panel");
    const panelTitle = root.querySelector(".vehicle-filter-panel-title");
    const panelOptions = root.querySelector(".vehicle-filter-options");
    const panelClose = root.querySelector(".vehicle-filter-panel-close");

    const labels = config.labels || {};
    const modelMap = config.modelMap || {};
    const generationMap = config.generationMap || {};

    let activeTier = null;

    function tierValue(tier) {
      if (tier === "make") return makeInput.value;
      if (tier === "model") return modelInput.value;
      return generationInput.value;
    }

    function setTierValue(tier, value) {
      if (tier === "make") makeInput.value = value;
      else if (tier === "model") modelInput.value = value;
      else generationInput.value = value;
    }

    function chipLabel(tier) {
      const label = labels[tier] || tier;
      const value = tierValue(tier);
      return value ? label + " " + value : label;
    }

    function updateChips() {
      makeChip.textContent = chipLabel("make");
      modelChip.textContent = chipLabel("model");
      generationChip.textContent = chipLabel("generation");

      const hasMake = Boolean(makeInput.value);
      const hasModel = Boolean(modelInput.value);

      modelChip.disabled = !hasMake;
      generationChip.disabled = !hasModel;

      makeChip.classList.toggle("is-active", Boolean(makeInput.value));
      modelChip.classList.toggle("is-active", Boolean(modelInput.value));
      generationChip.classList.toggle("is-active", Boolean(generationInput.value));
      modelChip.classList.toggle("is-muted", !hasMake);
      generationChip.classList.toggle("is-muted", !hasModel);
    }

    function optionsForTier(tier) {
      if (tier === "make") {
        return (config.makes || []).slice().sort((a, b) => a.localeCompare(b, "ru"));
      }
      if (tier === "model") {
        const make = makeInput.value;
        return make ? (modelMap[make] || []).slice() : [];
      }
      if (tier === "generation") {
        const make = makeInput.value;
        const model = modelInput.value;
        return make && model ? (generationMap[make]?.[model] || []).slice() : [];
      }
      return [];
    }

    function closePanel() {
      activeTier = null;
      panel.hidden = true;
      root.classList.remove("is-panel-open");
    }

    function openPanel(tier) {
      if (tier === "model" && !makeInput.value) return;
      if (tier === "generation" && !modelInput.value) return;
      activeTier = tier;
      panel.hidden = false;
      root.classList.add("is-panel-open");
      panelTitle.textContent = labels[tier] || tier;
      panelOptions.innerHTML = "";

      const anyBtn = document.createElement("button");
      anyBtn.type = "button";
      anyBtn.className = "vehicle-filter-option vehicle-filter-option-any";
      anyBtn.textContent = tier === "generation" ? "Любое" : "Любая";
      anyBtn.addEventListener("click", () => {
        setTierValue(tier, "");
        if (tier === "make") {
          modelInput.value = "";
          generationInput.value = "";
        } else if (tier === "model") {
          generationInput.value = "";
        }
        updateChips();
        closePanel();
      });
      panelOptions.appendChild(anyBtn);

      optionsForTier(tier).forEach((optionValue) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "vehicle-filter-option";
        if (optionValue === tierValue(tier)) btn.classList.add("is-selected");
        btn.textContent = optionValue;
        btn.addEventListener("click", () => {
          setTierValue(tier, optionValue);
          if (tier === "make") {
            modelInput.value = "";
            generationInput.value = "";
          } else if (tier === "model") {
            generationInput.value = "";
          }
          updateChips();
          closePanel();
        });
        panelOptions.appendChild(btn);
      });
    }

    makeChip.addEventListener("click", () => openPanel("make"));
    modelChip.addEventListener("click", () => openPanel("model"));
    generationChip.addEventListener("click", () => openPanel("generation"));
    panelClose.addEventListener("click", closePanel);

    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) closePanel();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closePanel();
    });

    updateChips();
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
