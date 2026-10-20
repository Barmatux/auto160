(function () {
  const dialog = document.querySelector("[data-featured-dialog]");
  if (!dialog) return;

  const titleEl = dialog.querySelector("[data-featured-dialog-title]");
  const avbyLink = dialog.querySelector("[data-featured-avby-link]");
  const leadListingId = dialog.querySelector("[data-featured-lead-listing-id]");
  const leadAvbyUrl = dialog.querySelector("[data-featured-lead-avby-url]");
  const leadStatus = dialog.querySelector("[data-featured-lead-status]");
  const leadForm = dialog.querySelector("[data-featured-lead-form]");

  function closeDialog() {
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }

  function openForCard(card) {
    const url = card.getAttribute("data-avby-url") || "";
    const listingId = card.getAttribute("data-listing-id") || "";
    if (titleEl) {
      titleEl.textContent = "Перейти на объявление на av.by?";
    }
    if (avbyLink) {
      avbyLink.href = url || "#";
      avbyLink.toggleAttribute("hidden", !url);
    }
    if (leadListingId) leadListingId.value = listingId;
    if (leadAvbyUrl) leadAvbyUrl.value = url;
    if (leadStatus) {
      leadStatus.hidden = true;
      leadStatus.textContent = "";
    }
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
  }

  document.querySelectorAll("[data-featured-dialog-close]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      closeDialog();
    });
  });

  document.querySelectorAll("[data-featured-card]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        event.preventDefault();
      }
      openForCard(card);
    });
    const openBtn = card.querySelector("[data-featured-open]");
    if (openBtn) {
      openBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openForCard(card);
      });
    }
  });

  if (leadForm) {
    leadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const nameInput = leadForm.querySelector('[name="contact_name"]');
      const contactInput = leadForm.querySelector('[name="contact"]');
      const commentInput = leadForm.querySelector('[name="comment"]');
      const sourceInput = leadForm.querySelector('[name="source"]');
      const payload = {
        contact_name: (nameInput && nameInput.value) || "",
        contact: (contactInput && contactInput.value) || "",
        comment: (commentInput && commentInput.value) || null,
        listing_id: leadListingId && leadListingId.value ? Number(leadListingId.value) : null,
        avby_url: (leadAvbyUrl && leadAvbyUrl.value) || null,
        source: (sourceInput && sourceInput.value) || "featured_modal",
      };
      if (leadStatus) {
        leadStatus.hidden = false;
        leadStatus.textContent = "Отправка…";
      }
      try {
        const res = await fetch("/api/v1/public/leads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = data.detail;
          throw new Error(typeof detail === "string" ? detail : "Не удалось отправить заявку");
        }
        if (leadStatus) leadStatus.textContent = "Заявка отправлена. Мы свяжемся с вами.";
        if (nameInput) nameInput.value = "";
        if (contactInput) contactInput.value = "";
        if (commentInput) commentInput.value = "";
      } catch (err) {
        if (leadStatus) leadStatus.textContent = err.message || "Ошибка отправки";
      }
    });
  }
})();
