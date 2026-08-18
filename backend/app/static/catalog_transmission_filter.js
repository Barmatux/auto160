(function () {
  const AUTO_PARENT = "auto";
  const AUTO_SUBTYPES = ["auto-classic", "robot", "cvt"];
  const MANUAL = "manual";

  function initTransmissionFilter(root) {
    const trigger = root.querySelector(".catalog-transmission-trigger");
    const menu = root.querySelector(".catalog-transmission-menu");
    const labelNode = root.querySelector(".catalog-transmission-trigger-label");
    const valuesHost = root.querySelector(".catalog-transmission-values");
    const parentInput = root.querySelector('[data-transmission-role="parent"]');
    const subtypeInputs = Array.from(root.querySelectorAll('[data-transmission-role="subtype"]'));
    const manualInput = root.querySelector('[data-transmission-role="manual"]');
    const rows = Array.from(root.querySelectorAll(".catalog-transmission-row"));

    if (!trigger || !menu || !valuesHost || !parentInput) {
      return;
    }

    function rowForInput(input) {
      return input ? input.closest(".catalog-transmission-row") : null;
    }

    function setRowSelected(input, selected) {
      const row = rowForInput(input);
      if (row) {
        row.classList.toggle("is-selected", selected);
      }
    }

    function refreshRowStates() {
      rows.forEach((row) => {
        const input = row.querySelector('input[type="checkbox"]');
        if (input) {
          setRowSelected(input, input.checked);
        }
      });
      root.classList.toggle("is-active", valuesHost.children.length > 0);
    }

    function buildDisplayLabel() {
      const labels = [];
      if (parentInput.checked) {
        labels.push(parentInput.dataset.label || "автомат");
      } else {
        subtypeInputs.forEach((input) => {
          if (input.checked) {
            labels.push(input.dataset.label || input.value);
          }
        });
      }
      if (manualInput && manualInput.checked) {
        labels.push(manualInput.dataset.label || "механика");
      }
      return labels.length ? labels.join(", ") : "Любая";
    }

    function syncHiddenInputs() {
      valuesHost.replaceChildren();
      if (parentInput.checked) {
        valuesHost.appendChild(createHiddenInput(AUTO_PARENT));
      } else {
        subtypeInputs.forEach((input) => {
          if (input.checked) {
            valuesHost.appendChild(createHiddenInput(input.value));
          }
        });
      }
      if (manualInput && manualInput.checked) {
        valuesHost.appendChild(createHiddenInput(MANUAL));
      }
      labelNode.textContent = buildDisplayLabel();
      refreshRowStates();
    }

    function createHiddenInput(value) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "transmission";
      input.value = value;
      return input;
    }

    function setAutoGroupChecked(checked) {
      parentInput.checked = checked;
      subtypeInputs.forEach((input) => {
        input.checked = checked;
      });
    }

    function syncParentFromSubtypes() {
      const allChecked = subtypeInputs.every((input) => input.checked);
      parentInput.checked = allChecked;
    }

    parentInput.addEventListener("change", () => {
      setAutoGroupChecked(parentInput.checked);
      syncHiddenInputs();
    });

    subtypeInputs.forEach((input) => {
      input.addEventListener("change", () => {
        if (parentInput.checked && !input.checked) {
          parentInput.checked = false;
          subtypeInputs.forEach((subtype) => {
            if (subtype !== input) {
              subtype.checked = true;
            }
          });
        } else {
          syncParentFromSubtypes();
        }
        syncHiddenInputs();
      });
    });

    if (manualInput) {
      manualInput.addEventListener("change", syncHiddenInputs);
    }

    trigger.addEventListener("click", () => {
      const willOpen = menu.hidden;
      closeAllMenus();
      menu.hidden = !willOpen;
      trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });

    root.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) {
        menu.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      }
    });

    syncHiddenInputs();
  }

  function closeAllMenus() {
    document.querySelectorAll(".catalog-transmission-dropdown").forEach((root) => {
      const menu = root.querySelector(".catalog-transmission-menu");
      const trigger = root.querySelector(".catalog-transmission-trigger");
      if (menu) {
        menu.hidden = true;
      }
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".catalog-transmission-dropdown")) {
      closeAllMenus();
    }
  });

  document.querySelectorAll("[data-transmission-filter]").forEach(initTransmissionFilter);
})();
