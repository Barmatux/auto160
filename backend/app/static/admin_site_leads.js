(function () {
  function numOrNull(v) {
    const s = String(v || "").trim().replace(",", ".");
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  document.querySelectorAll("[data-lead-save]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-lead-save");
      const row = btn.closest("tr");
      const msg = row.querySelector("[data-lead-msg]");
      const field = (name) => row.querySelector('[data-lead-field="' + name + '"]');
      const payload = {
        status: field("status").value,
        deal_amount: numOrNull(field("deal_amount").value),
        deal_margin: numOrNull(field("deal_margin").value),
        deal_currency: field("deal_currency").value || null,
        manager_note: field("manager_note").value,
      };
      btn.disabled = true;
      msg.textContent = "";
      try {
        const res = await fetch("/api/v1/admin/site-leads/" + id, {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Ошибка");
        row.classList.remove("is-unread");
        msg.textContent = "Сохранено";
        setTimeout(() => window.location.reload(), 600);
      } catch (err) {
        msg.textContent = err.message || "Ошибка";
      } finally {
        btn.disabled = false;
      }
    });
  });
})();
