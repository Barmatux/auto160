(function () {
  async function api(url, options) {
    const res = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options && options.headers) },
      ...options,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Ошибка");
    }
    return data;
  }

  const addForm = document.querySelector("[data-featured-add-form]");
  if (addForm) {
    const status = addForm.querySelector("[data-featured-add-status]");
    addForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(addForm);
      if (status) {
        status.hidden = false;
        status.textContent = "Сохраняем…";
      }
      try {
        await api("/api/v1/admin/featured-listings", {
          method: "POST",
          body: JSON.stringify({
            listing_id: Number(fd.get("listing_id")),
            sort_weight: Number(fd.get("sort_weight") || 0),
          }),
        });
        window.location.reload();
      } catch (err) {
        if (status) status.textContent = err.message || "Ошибка";
      }
    });
  }

  document.querySelectorAll("[data-featured-deactivate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-featured-deactivate");
      try {
        await api("/api/v1/admin/featured-listings/" + id + "/active", {
          method: "POST",
          body: JSON.stringify({ is_active: false }),
        });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });

  document.querySelectorAll("[data-featured-activate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-featured-activate");
      try {
        await api("/api/v1/admin/featured-listings/" + id + "/active", {
          method: "POST",
          body: JSON.stringify({ is_active: true }),
        });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });

  document.querySelectorAll("[data-featured-remove]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-featured-remove");
      if (!window.confirm("Удалить из подборки?")) return;
      try {
        await api("/api/v1/admin/featured-listings/" + id, { method: "DELETE" });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });
})();
