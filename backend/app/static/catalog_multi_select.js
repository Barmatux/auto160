(function () {
  function initMultiSelect(root) {
    const hierarchical = root.dataset.hierarchical || "";
    if (hierarchical === "location") {
      initLocationMultiSelect(root);
      return;
    }
    if (hierarchical === "transmission") {
      initTransmissionMultiSelect(root);
      return;
    }
    initFlatMultiSelect(root);
  }

  function initFlatMultiSelect(root) {
    const trigger = root.querySelector(".catalog-multi-select-trigger");
    const menu = root.querySelector(".catalog-multi-select-menu");
    const labelNode = root.querySelector(".catalog-multi-select-trigger-label");
    const valuesHost = root.querySelector(".catalog-multi-select-values");
    const paramName = root.dataset.paramName || "";
    const placeholder = root.dataset.placeholder || "Любой";
    const optionInputs = Array.from(root.querySelectorAll('[data-multi-select-role="option"]'));

    if (!trigger || !menu || !valuesHost || !labelNode || !paramName) {
      return;
    }

    if (root.dataset.menuFit === "content") {
      menu.classList.add("is-fit-content");
    }

    function syncHiddenInputs() {
      valuesHost.replaceChildren();
      optionInputs.forEach((input) => {
        if (input.checked) {
          valuesHost.appendChild(createHiddenInput(paramName, input.value));
        }
      });
      labelNode.textContent = formatSelectionLabel(
        optionInputs.filter((input) => input.checked).map((input) => input.dataset.label || input.value),
        placeholder
      );
      refreshRowStates(root, optionInputs);
      root.classList.toggle("is-active", valuesHost.children.length > 0);
    }

    mountCommonMultiSelect(root, {
      trigger,
      menu,
      syncHiddenInputs,
      bindInputs: () => {
        optionInputs.forEach((input) => {
          input.addEventListener("change", syncHiddenInputs);
        });
      },
      referenceSelect: () => referenceSelect(root),
    });
  }

  function initTransmissionMultiSelect(root) {
    const trigger = root.querySelector(".catalog-multi-select-trigger");
    const menu = root.querySelector(".catalog-multi-select-menu");
    const labelNode = root.querySelector(".catalog-multi-select-trigger-label");
    const valuesHost = root.querySelector(".catalog-multi-select-values");
    const paramName = root.dataset.paramName || "";
    const placeholder = root.dataset.placeholder || "Любой";
    const parentInput = root.querySelector('[data-multi-select-role="parent"]');
    const subtypeInputs = Array.from(root.querySelectorAll('[data-multi-select-role="subtype"]'));
    const manualInput = root.querySelector('[data-multi-select-role="manual"]');

    if (!trigger || !menu || !valuesHost || !labelNode || !paramName) {
      return;
    }

    if (root.dataset.menuFit === "content") {
      menu.classList.add("is-fit-content");
    }

    function allInputs() {
      const list = [];
      if (parentInput) {
        list.push(parentInput);
      }
      list.push(...subtypeInputs);
      if (manualInput) {
        list.push(manualInput);
      }
      return list;
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

    function syncHiddenInputs() {
      valuesHost.replaceChildren();
      if (parentInput && parentInput.checked) {
        valuesHost.appendChild(createHiddenInput(paramName, "auto"));
      } else {
        subtypeInputs.forEach((input) => {
          if (input.checked) {
            valuesHost.appendChild(createHiddenInput(paramName, input.value));
          }
        });
      }
      if (manualInput && manualInput.checked) {
        valuesHost.appendChild(createHiddenInput(paramName, manualInput.value));
      }

      const labels = [];
      if (parentInput && parentInput.checked) {
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
      labelNode.textContent = formatSelectionLabel(labels, placeholder);
      refreshRowStates(root, allInputs());
      root.classList.toggle("is-active", valuesHost.children.length > 0);
    }

    mountCommonMultiSelect(root, {
      trigger,
      menu,
      labelNode,
      valuesHost,
      placeholder,
      referenceSelect: () => referenceSelect(root),
      syncHiddenInputs,
      bindInputs: () => {
        if (parentInput) {
          parentInput.addEventListener("change", () => {
            setAutoGroupChecked(parentInput.checked);
            syncHiddenInputs();
          });
        }
        subtypeInputs.forEach((input) => {
          input.addEventListener("change", () => {
            if (parentInput && parentInput.checked && !input.checked) {
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
      },
    });
  }

  function initLocationMultiSelect(root) {
    const trigger = root.querySelector(".catalog-multi-select-trigger");
    const menu = root.querySelector(".catalog-multi-select-menu");
    const labelNode = root.querySelector(".catalog-multi-select-trigger-label");
    const valuesHost = root.querySelector(".catalog-multi-select-values");
    const regionParam = root.dataset.paramRegion || "region";
    const cityParam = root.dataset.paramCity || "city";
    const placeholder = root.dataset.placeholder || "Любой";
    const standaloneInput = root.querySelector('[data-multi-select-role="standalone"]');
    const regionGroups = Array.from(root.querySelectorAll(".catalog-multi-select-region-group"));

    if (!trigger || !menu || !valuesHost || !labelNode) {
      return;
    }

    function groupParts(group) {
      return {
        regionInput: group.querySelector('[data-multi-select-role="region"]'),
        cityInputs: Array.from(group.querySelectorAll('[data-multi-select-role="city"]')),
        expandButton: group.querySelector(".catalog-multi-select-expand"),
        citiesHost: group.querySelector(".catalog-multi-select-region-cities"),
      };
    }

    function setRegionGroupChecked(group, checked) {
      const { regionInput, cityInputs } = groupParts(group);
      if (regionInput) {
        regionInput.checked = checked;
      }
      cityInputs.forEach((input) => {
        input.checked = checked;
      });
    }

    function syncRegionFromCities(group) {
      const { regionInput, cityInputs } = groupParts(group);
      if (!regionInput || cityInputs.length === 0) {
        return;
      }
      regionInput.checked = cityInputs.every((input) => input.checked);
    }

    function toggleRegionExpanded(group, open) {
      const { expandButton, citiesHost } = groupParts(group);
      if (!citiesHost) {
        return;
      }
      const willOpen = open ?? citiesHost.hidden;
      citiesHost.hidden = !willOpen;
      group.classList.toggle("is-expanded", willOpen);
      if (expandButton) {
        expandButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
      }
    }

    function allInputs() {
      const list = [];
      if (standaloneInput) {
        list.push(standaloneInput);
      }
      regionGroups.forEach((group) => {
        const { regionInput, cityInputs } = groupParts(group);
        if (regionInput) {
          list.push(regionInput);
        }
        list.push(...cityInputs);
      });
      return list;
    }

    function syncHiddenInputs() {
      valuesHost.replaceChildren();
      const labels = [];

      if (standaloneInput && standaloneInput.checked) {
        valuesHost.appendChild(createHiddenInput(cityParam, standaloneInput.value));
        labels.push(standaloneInput.dataset.label || standaloneInput.value);
      }

      regionGroups.forEach((group) => {
        const { regionInput, cityInputs } = groupParts(group);
        if (!regionInput) {
          return;
        }
        if (regionInput.checked) {
          valuesHost.appendChild(createHiddenInput(regionParam, regionInput.value));
          labels.push(regionInput.dataset.label || regionInput.value);
          return;
        }
        cityInputs.forEach((input) => {
          if (input.checked) {
            valuesHost.appendChild(createHiddenInput(cityParam, input.value));
            labels.push(input.dataset.label || input.value);
          }
        });
      });

      labelNode.textContent = formatSelectionLabel(labels, placeholder);
      refreshRowStates(root, allInputs());
      root.classList.toggle(
        "is-active",
        Boolean(standaloneInput && standaloneInput.checked)
          || regionGroups.some((group) => {
            const { regionInput, cityInputs } = groupParts(group);
            return (regionInput && regionInput.checked) || cityInputs.some((input) => input.checked);
          })
      );
    }

    mountCommonMultiSelect(root, {
      trigger,
      menu,
      labelNode,
      valuesHost,
      placeholder,
      referenceSelect: () => referenceSelect(root),
      syncHiddenInputs,
      bindInputs: () => {
        if (standaloneInput) {
          standaloneInput.addEventListener("change", syncHiddenInputs);
        }
        regionGroups.forEach((group) => {
          const { regionInput, cityInputs, expandButton } = groupParts(group);
          if (regionInput) {
            regionInput.addEventListener("change", () => {
              setRegionGroupChecked(group, regionInput.checked);
              syncHiddenInputs();
            });
          }
          cityInputs.forEach((input) => {
            input.addEventListener("change", () => {
              if (regionInput && regionInput.checked && !input.checked) {
                regionInput.checked = false;
                cityInputs.forEach((cityInput) => {
                  if (cityInput !== input) {
                    cityInput.checked = true;
                  }
                });
              } else {
                syncRegionFromCities(group);
              }
              syncHiddenInputs();
            });
          });
          if (expandButton) {
            expandButton.addEventListener("click", (event) => {
              event.preventDefault();
              event.stopPropagation();
              toggleRegionExpanded(group);
            });
          }
        });
      },
    });

    regionGroups.forEach((group) => {
      const { cityInputs } = groupParts(group);
      const hasCheckedCity = cityInputs.some((input) => input.checked);
      const regionChecked = group.querySelector('[data-multi-select-role="region"]')?.checked;
      if (hasCheckedCity && !regionChecked) {
        toggleRegionExpanded(group, true);
      }
    });
  }

  function mountCommonMultiSelect(root, config) {
    const { trigger, menu, syncHiddenInputs, bindInputs, referenceSelect } = config;

    function setMenuOpen(open) {
      root.classList.toggle("is-open", open);
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        syncTriggerHeight(root, trigger, referenceSelect);
      }
    }

    function toggleMenu() {
      const willOpen = !root.classList.contains("is-open");
      closeAllMenus();
      setMenuOpen(willOpen);
    }

    bindInputs();
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
    syncTriggerHeight(root, trigger, referenceSelect);
    window.addEventListener("resize", () => syncTriggerHeight(root, trigger, referenceSelect));
  }

  function referenceSelect(root) {
    const form = root.closest("form");
    if (!form) {
      return null;
    }
    return (
      form.querySelector('select[name="export_country"]')
      || form.querySelector('select[name="year_from"]')
      || form.querySelector("select")
    );
  }

  function syncTriggerHeight(root, trigger, referenceSelectFn) {
    const ref = referenceSelectFn();
    if (!ref) {
      return;
    }
    const height = ref.getBoundingClientRect().height;
    trigger.style.height = `${height}px`;
    trigger.style.minHeight = `${height}px`;
    trigger.style.maxHeight = `${height}px`;
  }

  function setRowSelected(input, selected) {
    const row = input ? input.closest(".catalog-multi-select-row") : null;
    if (row) {
      row.classList.toggle("is-selected", selected);
    }
  }

  function refreshRowStates(root, inputs) {
    inputs.forEach((input) => setRowSelected(input, input.checked));
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

  function createHiddenInput(name, value) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    return input;
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
