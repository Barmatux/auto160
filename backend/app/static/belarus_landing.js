(function () {
  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      throw new Error(typeof detail === "string" ? detail : "Запрос не выполнен");
    }
    return data;
  }

  const leadForm = document.querySelector("[data-belarus-lead-form]");
  if (leadForm) {
    const status = leadForm.querySelector("[data-belarus-lead-status]");
    leadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(leadForm);
      if (status) {
        status.hidden = false;
        status.textContent = "Отправка…";
      }
      try {
        await postJson("/api/v1/public/leads", {
          contact_name: fd.get("contact_name") || "",
          contact: fd.get("contact") || "",
          comment: fd.get("comment") || null,
          source: fd.get("source") || "belarus_landing",
        });
        if (status) status.textContent = "Заявка отправлена. Мы свяжемся с вами.";
        leadForm.reset();
      } catch (err) {
        if (status) status.textContent = err.message || "Ошибка отправки";
      }
    });
  }

  const importForm = document.querySelector("[data-import-date-form]");
  const importResult = document.querySelector("[data-import-date-result]");
  if (importForm && importResult) {
    importForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(importForm);
      importResult.hidden = false;
      importResult.textContent = "Проверяем…";
      try {
        const data = await postJson("/api/v1/public/import-date", {
          query: fd.get("query") || "",
        });
        if (!data.ok) {
          importResult.textContent = data.message || "Не удалось проверить";
          return;
        }
        if (data.release_date) {
          importResult.textContent = "Дата ввоза в РБ: " + data.release_date;
          return;
        }
        importResult.textContent = data.message || "Дата ввоза не найдена";
      } catch (err) {
        importResult.textContent = err.message || "Ошибка проверки";
      }
    });
  }

  const consultForm = document.querySelector("[data-belarus-consult-form]");
  const consultDialog = document.querySelector("[data-belarus-consult-dialog]");
  const consultStatus = consultForm && consultForm.querySelector("[data-belarus-consult-status]");
  const consultUrlPreview = document.querySelector("[data-belarus-consult-url-preview]");
  const consultAvbyInput = document.querySelector("[data-belarus-consult-avby-url]");
  const consultLeadForm = document.querySelector("[data-belarus-consult-lead-form]");
  const consultLeadStatus =
    consultLeadForm && consultLeadForm.querySelector("[data-belarus-consult-lead-status]");

  function openConsultDialog(avbyUrl) {
    if (!consultDialog) return;
    if (consultUrlPreview) consultUrlPreview.textContent = avbyUrl;
    if (consultAvbyInput) consultAvbyInput.value = avbyUrl;
    if (consultLeadStatus) {
      consultLeadStatus.hidden = true;
      consultLeadStatus.textContent = "";
    }
    if (consultLeadForm) consultLeadForm.reset();
    if (consultAvbyInput) consultAvbyInput.value = avbyUrl;
    if (typeof consultDialog.showModal === "function") {
      consultDialog.showModal();
    } else {
      consultDialog.setAttribute("open", "");
    }
  }

  function closeConsultDialog() {
    if (!consultDialog) return;
    if (typeof consultDialog.close === "function") {
      consultDialog.close();
    } else {
      consultDialog.removeAttribute("open");
    }
  }

  if (consultForm && consultDialog) {
    consultForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const fd = new FormData(consultForm);
      const avbyUrl = String(fd.get("avby_url") || "").trim();
      if (!avbyUrl) {
        if (consultStatus) {
          consultStatus.hidden = false;
          consultStatus.textContent = "Вставьте ссылку на объявление";
        }
        return;
      }
      if (consultStatus) consultStatus.hidden = true;
      openConsultDialog(avbyUrl);
    });

    consultDialog.querySelectorAll("[data-belarus-consult-close]").forEach((btn) => {
      btn.addEventListener("click", closeConsultDialog);
    });
    consultDialog.addEventListener("click", (event) => {
      if (event.target === consultDialog) closeConsultDialog();
    });

    const openChatBtn = consultDialog.querySelector("[data-belarus-consult-open-chat]");
    if (openChatBtn) {
      openChatBtn.addEventListener("click", () => {
        const avbyUrl = (consultAvbyInput && consultAvbyInput.value) || "";
        closeConsultDialog();
        window.dispatchEvent(
          new CustomEvent("auto160:open-chat", {
            detail: {
              message:
                "Здравствуйте! Нужна консультация по авто из Беларуси." +
                (avbyUrl ? " Ссылка: " + avbyUrl : ""),
              avby_url: avbyUrl || null,
            },
          })
        );
      });
    }
  }

  if (consultLeadForm) {
    consultLeadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(consultLeadForm);
      if (consultLeadStatus) {
        consultLeadStatus.hidden = false;
        consultLeadStatus.textContent = "Отправка…";
        consultLeadStatus.style.color = "";
      }
      try {
        const avbyUrl = String(fd.get("avby_url") || "").trim();
        const commentParts = [];
        const comment = String(fd.get("comment") || "").trim();
        if (comment) commentParts.push(comment);
        if (avbyUrl) commentParts.push("Ссылка: " + avbyUrl);
        await postJson("/api/v1/public/leads", {
          contact_name: fd.get("contact_name") || "",
          contact: fd.get("contact") || "",
          comment: commentParts.join("\n") || null,
          avby_url: avbyUrl || null,
          source: fd.get("source") || "belarus_consultation",
        });
        if (consultLeadStatus) {
          consultLeadStatus.textContent = "Заявка отправлена. Мы свяжемся с вами.";
        }
        consultLeadForm.querySelector('button[type="submit"]').disabled = true;
      } catch (err) {
        if (consultLeadStatus) {
          consultLeadStatus.textContent = err.message || "Ошибка отправки";
          consultLeadStatus.style.color = "#f87171";
        }
      }
    });
  }
})();
