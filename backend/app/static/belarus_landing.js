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
})();
