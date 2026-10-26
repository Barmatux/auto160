(function () {
  async function api(url, options) {
    var res = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options && options.headers) },
      ...options,
    });
    if (res.status === 204) return null;
    var data = await res.json().catch(function () {
      return {};
    });
    if (!res.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Ошибка");
    }
    return data;
  }

  function numOrNull(value) {
    if (value === "" || value == null) return null;
    var n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  var addForm = document.querySelector("[data-customs-add-form]");
  if (addForm) {
    var status = addForm.querySelector("[data-customs-add-status]");
    addForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var fd = new FormData(addForm);
      if (status) {
        status.hidden = false;
        status.textContent = "Сохраняем…";
      }
      try {
        await api("/api/v1/admin/customs-vehicles", {
          method: "POST",
          body: JSON.stringify({
            make: String(fd.get("make") || ""),
            model: String(fd.get("model") || ""),
            generation: String(fd.get("generation") || "") || null,
            year_from: numOrNull(fd.get("year_from")),
            year_to: numOrNull(fd.get("year_to")),
            engine_cc: Number(fd.get("engine_cc")),
            power_hp: Number(fd.get("power_hp")),
            engine_kind: String(fd.get("engine_kind") || "ice"),
            fuel_label: String(fd.get("fuel_label") || "") || null,
            notes: String(fd.get("notes") || "") || null,
            sort_weight: Number(fd.get("sort_weight") || 0),
            is_active: true,
          }),
        });
        window.location.reload();
      } catch (err) {
        if (status) status.textContent = err.message || "Ошибка";
      }
    });
  }

  document.querySelectorAll("[data-customs-deactivate]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var id = btn.getAttribute("data-customs-deactivate");
      try {
        await api("/api/v1/admin/customs-vehicles/" + id, {
          method: "PATCH",
          body: JSON.stringify({ is_active: false }),
        });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });

  document.querySelectorAll("[data-customs-activate]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var id = btn.getAttribute("data-customs-activate");
      try {
        await api("/api/v1/admin/customs-vehicles/" + id, {
          method: "PATCH",
          body: JSON.stringify({ is_active: true }),
        });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });

  document.querySelectorAll("[data-customs-remove]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var id = btn.getAttribute("data-customs-remove");
      if (!window.confirm("Удалить комплектацию?")) return;
      try {
        await api("/api/v1/admin/customs-vehicles/" + id, { method: "DELETE" });
        window.location.reload();
      } catch (err) {
        alert(err.message || "Ошибка");
      }
    });
  });
})();
