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

  function wrapSelection(textarea, before, after) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const val = textarea.value;
    const sel = val.slice(start, end) || "текст";
    textarea.value = val.slice(0, start) + before + sel + after + val.slice(end);
    const pos = start + before.length + sel.length + after.length;
    textarea.focus();
    textarea.setSelectionRange(pos, pos);
  }

  const bodyField = document.querySelector("[data-blog-body]");
  const toolbar = document.querySelector("[data-blog-toolbar]");
  if (toolbar && bodyField) {
    toolbar.querySelectorAll("[data-before]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const before = btn.getAttribute("data-before") || "";
        const after = btn.getAttribute("data-after") || "";
        wrapSelection(bodyField, before, after);
      });
    });
  }

  const titleField = document.querySelector("[data-blog-title]");
  const slugField = document.querySelector("[data-blog-slug]");
  if (titleField && slugField) {
    let slugTouched = Boolean(slugField.value.trim());
    slugField.addEventListener("input", () => {
      slugTouched = true;
    });
    titleField.addEventListener("blur", () => {
      if (!slugTouched && !slugField.value.trim() && titleField.value.trim()) {
        slugField.placeholder = "заполнится при сохранении";
      }
    });
  }

  const editForm = document.querySelector("[data-blog-edit-form]");
  if (editForm) {
    const status = editForm.querySelector("[data-blog-edit-status]");
    const postId = (editForm.getAttribute("data-post-id") || "").trim();

    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(editForm);
      const payload = {
        title: String(fd.get("title") || "").trim(),
        slug: String(fd.get("slug") || "").trim() || null,
        excerpt: String(fd.get("excerpt") || "").trim() || null,
        body: String(fd.get("body") || ""),
        is_published: Boolean(fd.get("is_published")),
      };
      if (status) {
        status.hidden = false;
        status.textContent = "Сохраняем…";
      }
      try {
        if (postId) {
          await api("/api/v1/admin/blog-posts/" + postId, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });
          window.location.href = "/admin/blog/" + postId + "/edit";
        } else {
          const created = await api("/api/v1/admin/blog-posts", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          window.location.href = "/admin/blog/" + created.id + "/edit";
        }
      } catch (err) {
        if (status) status.textContent = err.message || "Ошибка";
      }
    });
  }

  document.querySelectorAll("[data-blog-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-blog-delete");
      if (!id || !window.confirm("Удалить статью?")) return;
      try {
        await api("/api/v1/admin/blog-posts/" + id, { method: "DELETE" });
        const row = document.querySelector('[data-blog-row="' + id + '"]');
        if (row) row.remove();
      } catch (err) {
        window.alert(err.message || "Ошибка");
      }
    });
  });
})();
