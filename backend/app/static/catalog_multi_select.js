(function () {
  function initMultiSelect(root) {
    const trigger = root.querySelector(".catalog-multi-select-trigger");
    const menu = root.querySelector(".catalog-multi-select-menu");
    const labelNode = root.querySelector(".catalog-multi-select-trigger-label");
    const valuesHost = root.querySelector(".catalog-multi-select-values");
    const paramName = root.dataset.paramName || "";
    const placeholder = root.dataset.placeholder || "Любой";
    const hierarchical = root.dataset.hierarchical === "transmission";
    const parentInput = hierarchical
      ? root.querySelector('[data-multi-select-role="parent"]')
      : null;
    const subtypeInputs = hierarchical
      ? Array.from(root.querySelectorAll('[data-multi-select-role="subtype"]'))
      : [];
    const optionInputs = hierarchical
      ? []
      : Array.from(root.querySelectorAll('[data-multi-select-role="option"]'));

    if (!trigger || !menu || !valuesHost || !labelNode || !paramName) {
      return;
    }

    if (root.dataset.menuFit === "content") {
      menu.classList.add("is-fit-content");
    }

    function allInputs() {
      if (hierarchical) {
        const list = [];
        if (parentInput) {
          list.push(parentInput);
        }
        list.push(...subtypeInputs);
        const manual = root.querySelector('[data-multi-select-role="manual"]');
        if (manual) {
          list.push(manual);
        }
        return list;
      }
      return optionInputs;
    }

    function referenceSelect() {
      const form = root.closest("form");
      if (!form) {
        return null;
      }
      return (
        form.querySelector('select[name="export_country"]')
        || form.querySelector('select[name="city"]')
        || form.querySelector("select")
      );
    }

    function syncTriggerHeight() {
      const ref = referenceSelect();
      if (!ref) {
        return;
      }
      const height = ref.getBoundingClientRect().height;
      trigger.style.height = `${height}px`;
      trigger.style.minHeight = `${height}px`;
      trigger.style.maxHeight = `${height}px`;
    }

    function setMenuOpen(open) {
      root.classList.toggle("is-open", open);
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        syncTriggerHeight();
      }
    }

    function setRowSelected(input, selected) {
      const row = input ? input.closest(".catalog-multi-select-row") : null;
      if (row) {
        row.classList.toggle("is-selected", selected);
      }
    }

    function refreshRowStates() {
      allInputs().forEach((input) => setRowSelected(input, input.checked));
      root.classList.toggle("is-active", valuesHost.children.length > 0);
    }

    function formatSelectionLabel(labels, emptyPlaceholder) {
      if (!labels.length) {
        return emptyPlaceholder;
      }
      if (labels.length === 1) {
        return labels[0];
      }
      return `Выбрано пунктов: ${labels.length}`;
    }

    function buildDisplayLabel() {
      const labels = [];
      if (hierarchical) {
        if (parentInput && parentInput.checked) {
          labels.push(parentInput.dataset.label || "автомат");
        } else {
          subtypeInputs.forEach((input) => {
            if (input.checked) {
              labels.push(input.dataset.label || input.value);
            }
          });
        }
        const manual = root.querySelector('[data-multi-select-role="manual"]');
        if (manual && manual.checked) {
          labels.push(manual.dataset.label || "механика");
        }
      } else {
        allInputs().forEach((input) => {
          if (input.checked) {
            labels.push(input.dataset.label || input.value);
          }
        });
      }
      return formatSelectionLabel(labels, placeholder);
    }

    function syncHiddenInputs() {
      valuesHost.replaceChildren();
      if (hierarchical) {
        if (parentInput && parentInput.checked) {
          valuesHost.appendChild(createHiddenInput("auto"));
        } else {
          subtypeInputs.forEach((input) => {
            if (input.checked) {
              valuesHost.appendChild(createHiddenInput(input.value));
            }
          });
        }
        const manual = root.querySelector('[data-multi-select-role="manual"]');
        if (manual && manual.checked) {
          valuesHost.appendChild(createHiddenInput(manual.value));
        }
      } else {
        allInputs().forEach((input) => {
          if (input.checked) {
            valuesHost.appendChild(createHiddenInput(input.value));
          }
        });
      }
      labelNode.textContent = buildDisplayLabel();
      refreshRowStates();
    }

    function createHiddenInput(value) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = paramName;
      input.value = value;
      return input;
    }

    function setAutoGroupChecked(checked) {
      if (!parentInput) {
        return;
      }
      parentInput.checked = checked;
      subtypeInputs.forEach((input) => {
        input.checked = checked;
      });
    }

    function syncParentFromSubtypes() {
      if (!parentInput) {
        return;
      }
      parentInput.checked = subtypeInputs.length > 0 && subtypeInputs.every((input) => input.checked);
    }

    function toggleMenu() {
      const willOpen = !root.classList.contains("is-open");
      closeAllMenus();
      setMenuOpen(willOpen);
    }

    if (hierarchical && parentInput) {
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

      const manual = root.querySelector('[data-multi-select-role="manual"]');
      if (manual) {
        manual.addEventListener("change", syncHiddenInputs);
      }
    } else {
      optionInputs.forEach((input) => {
        input.addEventListener("change", syncHiddenInputs);
      });
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleMenu();
    });

    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleMenu();
      }
    });

    menu.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    root.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && root.classList.contains("is-open")) {
        setMenuOpen(false);
      }
    });

    setMenuOpen(false);
    syncHiddenInputs();
    syncTriggerHeight();
    window.addEventListener("resize", syncTriggerHeight);
  }

  function closeAllMenus() {
    document.querySelectorAll(".catalog-multi-select").forEach((root) => {
      const menu = root.querySelector(".catalog-multi-select-menu");
      const trigger = root.querySelector(".catalog-multi-select-trigger");
      root.classList.remove("is-open");
      if (menu) {
        menu.hidden = true;
      }
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".catalog-multi-select")) {
      closeAllMenus();
    }
  });

  function mountMultiSelects() {
    document.querySelectorAll("[data-catalog-multi-select]").forEach(initMultiSelect);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountMultiSelects);
  } else {
    mountMultiSelects();
  }
})();
