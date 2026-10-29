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

  function removeRow(listingId) {
    const row = document.querySelector('[data-eu-check-row="' + listingId + '"]');
    if (row) row.remove();
  }

  document.querySelectorAll("[data-eu-check-show]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-eu-check-show");
      btn.disabled = true;
      try {
        await api("/api/v1/admin/eu-check/" + id + "/show", { method: "POST", body: "{}" });
        removeRow(id);
      } catch (err) {
        btn.disabled = false;
        alert(err.message || "Ошибка");
      }
    });
  });

  document.querySelectorAll("[data-eu-check-hide]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-eu-check-hide");
      btn.disabled = true;
      try {
        await api("/api/v1/admin/eu-check/" + id + "/hide", { method: "POST", body: "{}" });
        removeRow(id);
      } catch (err) {
        btn.disabled = false;
        alert(err.message || "Ошибка");
      }
    });
  });
})();
