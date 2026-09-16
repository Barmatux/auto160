(function () {
  function closeAllVinCopyPopovers() {
    document.querySelectorAll(".admin-vin-copy-popover").forEach((popover) => {
      popover.hidden = true;
    });
  }

  async function adminFetch(url, options = {}) {
    let token = getCookie("access_token");
    if (!token) {
      const refreshed = await refreshAccessTokenIfNeeded();
      if (!refreshed) {
        window.location.href = "/login";
        return null;
      }
      token = getCookie("access_token");
    }
    return fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    });
  }

  async function copyVin(vin) {
    if (!vin) return false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(vin);
        return true;
      }
    } catch (_) {
      /* fallback below */
    }
    const textarea = document.createElement("textarea");
    textarea.value = vin;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (_) {
      copied = false;
    }
    textarea.remove();
    return copied;
  }

  function renderImportDateCell(cell, data) {
    cell.innerHTML = "";
    if (data.release_date) {
      const value = document.createElement("strong");
      value.className = "admin-vin-import-value";
      value.textContent = data.release_date;
      cell.appendChild(value);
      return;
    }

    const wrap = document.createElement("div");
    wrap.className = "admin-vin-import-missing";

    const label = document.createElement("span");
    label.className = "admin-vin-no-import";
    label.textContent = "Нет данных";
    wrap.appendChild(label);

    const listingId = cell.closest("tr")?.dataset.listingId;
    if (listingId) {
      const retryBtn = document.createElement("button");
      retryBtn.type = "button";
      retryBtn.className = "btn-link-like admin-vin-customs-retry";
      retryBtn.dataset.listingId = listingId;
      retryBtn.textContent = "Повторить запрос";
      wrap.appendChild(retryBtn);
      bindCustomsRetryButton(retryBtn);
    }

    if (data.customs_error) {
      const err = document.createElement("span");
      err.className = "admin-vin-customs-retry-error hint";
      err.textContent = data.customs_error;
      wrap.appendChild(err);
    }

    cell.appendChild(wrap);
  }

  async function runCustomsRecheck(button) {
    const listingId = button.dataset.listingId;
    const row = button.closest("tr");
    const cell = row?.querySelector("[data-import-cell]");
    if (!listingId || !cell) return;

    const errEl = cell.querySelector(".admin-vin-customs-retry-error");
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }

    button.disabled = true;
    const previousText = button.textContent;
    button.textContent = "Проверка…";

    const response = await adminFetch(`/api/v1/admin/listings/${listingId}/customs-recheck`, {
      method: "POST",
    });

    button.disabled = false;
    button.textContent = previousText;

    if (!response) return;

    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }

    if (!response.ok) {
      if (errEl) {
        errEl.textContent = data.detail || "Не удалось выполнить запрос";
        errEl.hidden = false;
      }
      return;
    }

    renderImportDateCell(cell, data);
  }

  function bindCustomsRetryButton(button) {
    button.addEventListener("click", () => runCustomsRecheck(button));
  }

  document.querySelectorAll(".admin-vin-code-cell").forEach((cell) => {
    const vinBtn = cell.querySelector(".admin-vin-code-btn");
    const popover = cell.querySelector(".admin-vin-copy-popover");
    const copyBtn = cell.querySelector(".admin-vin-copy-action");
    if (!vinBtn || !popover || !copyBtn) return;

    const openPopover = () => {
      closeAllVinCopyPopovers();
      popover.hidden = false;
    };

    vinBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      if (popover.hidden) {
        openPopover();
      } else {
        closeAllVinCopyPopovers();
      }
    });

    copyBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const vin = vinBtn.dataset.vin || vinBtn.textContent.trim();
      const copied = await copyVin(vin);
      copyBtn.textContent = copied ? "Скопировано" : "Ошибка";
      window.setTimeout(() => {
        copyBtn.textContent = "Скопировать";
        closeAllVinCopyPopovers();
      }, 900);
    });
  });

  document.querySelectorAll(".admin-vin-customs-retry").forEach(bindCustomsRetryButton);

  document.addEventListener("click", (event) => {
    if (event.target.closest(".admin-vin-code-cell")) return;
    closeAllVinCopyPopovers();
  });

  const MONTH_NAMES = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
  ];

  function parseIsoDate(value) {
    if (!value) return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]) - 1;
    const day = Number(match[3]);
    const date = new Date(year, month, day);
    if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) {
      return null;
    }
    return date;
  }

  function formatIsoDate(date) {
    if (!date) return "";
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function sameDay(a, b) {
    return (
      a &&
      b &&
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate()
    );
  }

  function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function buildVinFoundDateFilterUrl(fromDate, toDate) {
    const params = new URLSearchParams();
    if (fromDate) params.set("checked_from", formatIsoDate(fromDate));
    if (toDate) params.set("checked_to", formatIsoDate(toDate));
    const query = params.toString();
    return query ? `/admin/vin-check/found?${query}` : "/admin/vin-check/found";
  }

  function initDateFilterPopover() {
    const trigger = document.querySelector("[data-date-filter-trigger]");
    const popover = document.querySelector("[data-date-filter-popover]");
    if (!trigger || !popover) return;

    const grid = popover.querySelector("[data-date-grid]");
    const monthLabel = popover.querySelector("[data-date-month-label]");
    const applyBtn = popover.querySelector("[data-date-apply]");
    const clearBtn = popover.querySelector("[data-date-clear]");

    let rangeStart = parseIsoDate(popover.dataset.checkedFrom || "");
    let rangeEnd = parseIsoDate(popover.dataset.checkedTo || "");
    let pickingEnd = false;
    const initial = rangeStart || rangeEnd || new Date();
    let viewYear = initial.getFullYear();
    let viewMonth = initial.getMonth();

    function closePopover() {
      popover.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    function openPopover() {
      popover.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      renderCalendar();
    }

    function renderCalendar() {
      if (!grid || !monthLabel) return;
      monthLabel.textContent = `${MONTH_NAMES[viewMonth]} ${viewYear}`;
      grid.innerHTML = "";

      const firstDay = new Date(viewYear, viewMonth, 1);
      const startOffset = (firstDay.getDay() + 6) % 7;
      const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
      const selectedStart = rangeStart ? startOfDay(rangeStart) : null;
      const selectedEnd = rangeEnd ? startOfDay(rangeEnd) : selectedStart;
      const rangeLow =
        selectedStart && selectedEnd && selectedStart <= selectedEnd ? selectedStart : selectedEnd;
      const rangeHigh =
        selectedStart && selectedEnd && selectedStart <= selectedEnd ? selectedEnd : selectedStart;

      for (let i = 0; i < startOffset; i += 1) {
        const empty = document.createElement("span");
        empty.className = "admin-vin-date-cell is-empty";
        grid.appendChild(empty);
      }

      for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(viewYear, viewMonth, day);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "admin-vin-date-cell";
        button.textContent = String(day);
        button.dataset.iso = formatIsoDate(date);

        if (rangeLow && rangeHigh && date >= rangeLow && date <= rangeHigh) {
          button.classList.add("is-in-range");
        }
        if (sameDay(date, selectedStart)) button.classList.add("is-start");
        if (sameDay(date, selectedEnd)) button.classList.add("is-end");
        if (sameDay(date, new Date())) button.classList.add("is-today");

        button.addEventListener("click", () => {
          const picked = startOfDay(date);
          if (!pickingEnd || !rangeStart) {
            rangeStart = picked;
            rangeEnd = null;
            pickingEnd = true;
          } else {
            rangeEnd = picked;
            if (rangeStart > rangeEnd) {
              const tmp = rangeStart;
              rangeStart = rangeEnd;
              rangeEnd = tmp;
            }
            pickingEnd = false;
          }
          renderCalendar();
        });

        grid.appendChild(button);
      }
    }

    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      if (popover.hidden) {
        openPopover();
      } else {
        closePopover();
      }
    });

    popover.addEventListener("click", (event) => event.stopPropagation());

    popover.querySelectorAll("[data-date-nav]").forEach((button) => {
      button.addEventListener("click", () => {
        const delta = Number(button.dataset.dateNav || "0");
        viewMonth += delta;
        if (viewMonth < 0) {
          viewMonth = 11;
          viewYear -= 1;
        } else if (viewMonth > 11) {
          viewMonth = 0;
          viewYear += 1;
        }
        renderCalendar();
      });
    });

    applyBtn?.addEventListener("click", () => {
      if (!rangeStart && !rangeEnd) {
        window.location.href = "/admin/vin-check/found";
        return;
      }
      const fromDate = rangeStart || rangeEnd;
      const toDate = rangeEnd || rangeStart;
      window.location.href = buildVinFoundDateFilterUrl(fromDate, toDate);
    });

    clearBtn?.addEventListener("click", () => {
      window.location.href = "/admin/vin-check/found";
    });

    document.addEventListener("click", (event) => {
      if (event.target.closest(".admin-vin-date-filter-th")) return;
      closePopover();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closePopover();
    });
  }

  initDateFilterPopover();

  function initVinStatsModal() {
    const openBtn = document.querySelector("[data-vin-stats-open]");
    const modal = document.querySelector("[data-vin-stats-modal]");
    const backdrop = document.querySelector("[data-vin-stats-backdrop]");
    const closeBtn = document.querySelector("[data-vin-stats-close]");
    if (!openBtn || !modal || !backdrop) return;

    const open = () => {
      modal.hidden = false;
      backdrop.hidden = false;
      document.body.style.overflow = "hidden";
    };

    const close = () => {
      modal.hidden = true;
      backdrop.hidden = true;
      document.body.style.overflow = "";
    };

    openBtn.addEventListener("click", open);
    closeBtn?.addEventListener("click", close);
    backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) close();
    });
  }

  initVinStatsModal();
})();
