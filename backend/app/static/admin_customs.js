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

  var statusEl = document.querySelector("[data-customs-db-status]");
  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
    statusEl.style.color = isError ? "#f87171" : "";
  }

  var board = document.querySelector("[data-customs-db]");
  if (!board) return;

  var state = { makeId: null, modelId: null, literId: null };

  function litersLabel(value) {
    var n = Number(value);
    return (Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, "")) + " л";
  }

  function enableForm(selector, enabled) {
    var form = board.querySelector(selector);
    if (!form) return;
    form.querySelectorAll("input:not([type=hidden]), button").forEach(function (el) {
      el.disabled = !enabled;
    });
  }

  function setListEmpty(listName, text) {
    var list = board.querySelector('[data-list="' + listName + '"]');
    if (!list) return;
    list.innerHTML = '<li class="customs-db-empty">' + text + "</li>";
  }

  function renderList(listName, rows, renderItem) {
    var list = board.querySelector('[data-list="' + listName + '"]');
    if (!list) return;
    list.innerHTML = "";
    if (!rows.length) {
      setListEmpty(listName, "Пусто — добавьте запись");
      return;
    }
    rows.forEach(function (row) {
      list.appendChild(renderItem(row));
    });
  }

  function makeRow(label, selectAttr, selectId, delAttr, delId, active) {
    var li = document.createElement("li");
    if (active) li.classList.add("is-active");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "customs-db-item";
    btn.setAttribute(selectAttr, String(selectId));
    btn.innerHTML = "<span></span>";
    btn.querySelector("span").textContent = label;
    var del = document.createElement("button");
    del.type = "button";
    del.className = "btn-link customs-db-del";
    del.setAttribute(delAttr, String(delId));
    del.title = "Удалить";
    del.textContent = "×";
    li.appendChild(btn);
    li.appendChild(del);
    return li;
  }

  async function loadModels(makeId) {
    state.makeId = makeId;
    state.modelId = null;
    state.literId = null;
    board.querySelectorAll("[data-make-id]").forEach(function (el) {
      var li = el.closest("li");
      if (li) li.classList.toggle("is-active", el.getAttribute("data-make-id") === String(makeId));
    });
    var parent = board.querySelector("[data-parent-make]");
    if (parent) parent.value = String(makeId);
    enableForm('[data-add="model"]', true);
    enableForm('[data-add="liter"]', false);
    enableForm('[data-add="cc"]', false);
    setListEmpty("liters", "Выберите модель");
    setListEmpty("ccs", "Выберите объём в литрах");
    setListEmpty("models", "Загрузка…");
    try {
      var rows = await api("/api/v1/admin/customs-db/models?make_id=" + encodeURIComponent(makeId));
      renderList("models", rows, function (row) {
        return makeRow(row.name, "data-model-id", row.id, "data-del-model", row.id, false);
      });
    } catch (err) {
      setListEmpty("models", err.message || "Ошибка");
    }
  }

  async function loadLiters(modelId) {
    state.modelId = modelId;
    state.literId = null;
    board.querySelectorAll("[data-model-id]").forEach(function (el) {
      var li = el.closest("li");
      if (li) li.classList.toggle("is-active", el.getAttribute("data-model-id") === String(modelId));
    });
    var parent = board.querySelector("[data-parent-model]");
    if (parent) parent.value = String(modelId);
    enableForm('[data-add="liter"]', true);
    enableForm('[data-add="cc"]', false);
    setListEmpty("ccs", "Выберите объём в литрах");
    setListEmpty("liters", "Загрузка…");
    try {
      var rows = await api("/api/v1/admin/customs-db/liters?model_id=" + encodeURIComponent(modelId));
      renderList("liters", rows, function (row) {
        return makeRow(litersLabel(row.liters), "data-liter-id", row.id, "data-del-liter", row.id, false);
      });
    } catch (err) {
      setListEmpty("liters", err.message || "Ошибка");
    }
  }

  async function loadCcs(literId) {
    state.literId = literId;
    board.querySelectorAll("[data-liter-id]").forEach(function (el) {
      var li = el.closest("li");
      if (li) li.classList.toggle("is-active", el.getAttribute("data-liter-id") === String(literId));
    });
    var parent = board.querySelector("[data-parent-liter]");
    if (parent) parent.value = String(literId);
    enableForm('[data-add="cc"]', true);
    setListEmpty("ccs", "Загрузка…");
    try {
      var rows = await api("/api/v1/admin/customs-db/ccs?liter_id=" + encodeURIComponent(literId));
      renderList("ccs", rows, function (row) {
        var label = row.engine_cc + " см³";
        if (row.power_hp) label += " · " + row.power_hp + " л.с.";
        return makeRow(label, "data-cc-id", row.id, "data-del-cc", row.id, false);
      });
    } catch (err) {
      setListEmpty("ccs", err.message || "Ошибка");
    }
  }

  board.addEventListener("click", async function (event) {
    var delMake = event.target.closest("[data-del-make]");
    if (delMake) {
      if (!window.confirm("Удалить марку и всё внутри?")) return;
      try {
        await api("/api/v1/admin/customs-db/makes/" + delMake.getAttribute("data-del-make"), {
          method: "DELETE",
        });
        window.location.reload();
      } catch (err) {
        setStatus(err.message || "Ошибка", true);
      }
      return;
    }
    var delModel = event.target.closest("[data-del-model]");
    if (delModel) {
      if (!window.confirm("Удалить модель и всё внутри?")) return;
      try {
        await api("/api/v1/admin/customs-db/models/" + delModel.getAttribute("data-del-model"), {
          method: "DELETE",
        });
        if (state.makeId) loadModels(state.makeId);
      } catch (err) {
        setStatus(err.message || "Ошибка", true);
      }
      return;
    }
    var delLiter = event.target.closest("[data-del-liter]");
    if (delLiter) {
      if (!window.confirm("Удалить объём и точные см³?")) return;
      try {
        await api("/api/v1/admin/customs-db/liters/" + delLiter.getAttribute("data-del-liter"), {
          method: "DELETE",
        });
        if (state.modelId) loadLiters(state.modelId);
      } catch (err) {
        setStatus(err.message || "Ошибка", true);
      }
      return;
    }
    var delCc = event.target.closest("[data-del-cc]");
    if (delCc) {
      if (!window.confirm("Удалить точный объём?")) return;
      try {
        await api("/api/v1/admin/customs-db/ccs/" + delCc.getAttribute("data-del-cc"), {
          method: "DELETE",
        });
        if (state.literId) loadCcs(state.literId);
      } catch (err) {
        setStatus(err.message || "Ошибка", true);
      }
      return;
    }

    var makeBtn = event.target.closest("[data-make-id]");
    if (makeBtn) {
      loadModels(Number(makeBtn.getAttribute("data-make-id")));
      return;
    }
    var modelBtn = event.target.closest("[data-model-id]");
    if (modelBtn) {
      loadLiters(Number(modelBtn.getAttribute("data-model-id")));
      return;
    }
    var literBtn = event.target.closest("[data-liter-id]");
    if (literBtn) {
      loadCcs(Number(literBtn.getAttribute("data-liter-id")));
    }
  });

  function bindAddForm(selector, handler) {
    var form = board.querySelector(selector);
    if (!form) return;
    var busy = false;
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (busy) return;
      busy = true;
      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      setStatus("Сохраняем…");
      try {
        await handler(form, event);
        setStatus("");
      } catch (err) {
        setStatus(err.message || "Ошибка", true);
      } finally {
        busy = false;
        // Re-enable only if the column is still active (parent selected).
        if (btn && !btn.disabled) {
          /* keep */
        }
        if (selector === '[data-add="make"]' && btn) btn.disabled = false;
        if (selector === '[data-add="model"]' && btn && state.makeId) btn.disabled = false;
        if (selector === '[data-add="liter"]' && btn && state.modelId) btn.disabled = false;
        if (selector === '[data-add="cc"]' && btn && state.literId) btn.disabled = false;
        enableForm(selector, true);
        if (selector === '[data-add="model"]' && !state.makeId) enableForm(selector, false);
        if (selector === '[data-add="liter"]' && !state.modelId) enableForm(selector, false);
        if (selector === '[data-add="cc"]' && !state.literId) enableForm(selector, false);
      }
    });
  }

  bindAddForm('[data-add="make"]', async function (form) {
    var fd = new FormData(form);
    await api("/api/v1/admin/customs-db/makes", {
      method: "POST",
      body: JSON.stringify({ name: String(fd.get("name") || "") }),
    });
    window.location.reload();
  });

  bindAddForm('[data-add="model"]', async function (form) {
    if (!state.makeId) throw new Error("Сначала выберите марку слева");
    var fd = new FormData(form);
    var created = await api("/api/v1/admin/customs-db/models", {
      method: "POST",
      body: JSON.stringify({
        make_id: state.makeId,
        name: String(fd.get("name") || ""),
      }),
    });
    form.reset();
    board.querySelector("[data-parent-make]").value = String(state.makeId);
    await loadModels(state.makeId);
    setStatus("Модель «" + (created && created.name ? created.name : "") + "» сохранена");
  });

  bindAddForm('[data-add="liter"]', async function (form) {
    if (!state.modelId) throw new Error("Сначала выберите модель");
    var fd = new FormData(form);
    await api("/api/v1/admin/customs-db/liters", {
      method: "POST",
      body: JSON.stringify({
        model_id: state.modelId,
        liters: Number(fd.get("liters")),
      }),
    });
    form.reset();
    board.querySelector("[data-parent-model]").value = String(state.modelId);
    await loadLiters(state.modelId);
    setStatus("Объём сохранён");
  });

  bindAddForm('[data-add="cc"]', async function (form) {
    if (!state.literId) throw new Error("Сначала выберите объём в литрах");
    var fd = new FormData(form);
    var powerRaw = fd.get("power_hp");
    await api("/api/v1/admin/customs-db/ccs", {
      method: "POST",
      body: JSON.stringify({
        liter_id: state.literId,
        engine_cc: Number(fd.get("engine_cc")),
        power_hp: powerRaw === "" || powerRaw == null ? null : Number(powerRaw),
      }),
    });
    form.reset();
    board.querySelector("[data-parent-liter]").value = String(state.literId);
    await loadCcs(state.literId);
    setStatus("Точный объём сохранён");
  });
})();
