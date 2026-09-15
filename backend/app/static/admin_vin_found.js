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
})();
