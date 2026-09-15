(function () {
  function closeAllVinCopyPopovers() {
    document.querySelectorAll(".admin-vin-copy-popover").forEach((popover) => {
      popover.hidden = true;
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

  document.addEventListener("click", (event) => {
    if (event.target.closest(".admin-vin-code-cell")) return;
    closeAllVinCopyPopovers();
  });
})();
