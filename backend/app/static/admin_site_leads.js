(function () {
  document.querySelectorAll("[data-lead-mark-read]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-lead-mark-read");
      try {
        const res = await fetch("/api/v1/admin/site-leads/" + id + "/read", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_read: true }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Ошибка");
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });
})();
