(function () {
  const root = document.querySelector("[data-admin-messenger]");
  if (!root) return;

  const threadsEl = root.querySelector("[data-admin-threads]");
  const emptyEl = root.querySelector("[data-admin-empty]");
  const chatInner = root.querySelector("[data-admin-chat-inner]");
  const headerEl = root.querySelector("[data-admin-chat-header]");
  const messagesEl = root.querySelector("[data-admin-messages]");
  const compose = root.querySelector("[data-admin-compose]");
  const unreadOnly = root.querySelector("[data-admin-unread-only]");
  const refreshBtn = root.querySelector("[data-admin-refresh]");
  const badge = document.querySelector("[data-admin-msg-badge]");

  let activeId = null;
  let pollTimer = null;

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function api(path, opts) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opts,
    });
    if (!response.ok) {
      let detail = "Ошибка";
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return response.json();
  }

  function renderThreads(items) {
    if (!items.length) {
      threadsEl.innerHTML = '<p class="hint">Диалогов пока нет</p>';
      return;
    }
    threadsEl.innerHTML = items
      .map((t) => {
        const active = t.id === activeId ? " is-active" : "";
        const unread = t.unread_count > 0 ? `<span class="admin-msg-pill">${t.unread_count}</span>` : "";
        return `<button type="button" class="admin-messenger-thread${active}" data-thread-id="${t.id}">
          <div class="admin-messenger-thread-title">${esc(t.listing_title)} ${unread}</div>
          <div class="admin-messenger-thread-meta">${esc(t.contact_name)} · ${esc(t.contact_phone)}</div>
          <div class="admin-messenger-thread-preview">${esc(t.last_preview || "")}</div>
        </button>`;
      })
      .join("");
  }

  function renderChat(detail) {
    emptyEl.hidden = true;
    chatInner.hidden = false;
    headerEl.innerHTML = `<a href="${esc(detail.listing_url)}" target="_blank" rel="noopener">${esc(detail.listing_title)}</a>
      <div class="hint">${esc(detail.contact_name)} · ${esc(detail.contact_phone)}${detail.contact_email ? " · " + esc(detail.contact_email) : ""}</div>`;
    messagesEl.innerHTML = detail.messages
      .map((m) => {
        const side = m.sender === "manager" ? "me" : "them";
        const when = new Date(m.created_at).toLocaleString("ru-RU");
        return `<div class="admin-messenger-bubble admin-messenger-bubble-${side}">
          <div class="admin-messenger-bubble-body">${esc(m.body)}</div>
          <div class="admin-messenger-bubble-meta">${esc(when)}</div>
        </div>`;
      })
      .join("");
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function loadThreads() {
    const q = unreadOnly.checked ? "?unread_only=true" : "";
    const items = await api("/api/v1/admin/messages/threads" + q);
    renderThreads(items);
  }

  async function loadUnreadBadge() {
    try {
      const data = await api("/api/v1/admin/messages/unread-count");
      if (!badge) return;
      if (data.count > 0) {
        badge.hidden = false;
        badge.textContent = String(data.count);
      } else {
        badge.hidden = true;
      }
    } catch (_) {}
  }

  async function openThread(id) {
    activeId = id;
    const detail = await api(`/api/v1/admin/messages/threads/${id}`);
    renderChat(detail);
    await loadThreads();
    await loadUnreadBadge();
  }

  threadsEl.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-thread-id]");
    if (!btn) return;
    openThread(Number(btn.getAttribute("data-thread-id"))).catch((err) => alert(err.message));
  });

  compose.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!activeId) return;
    const textarea = compose.querySelector("textarea");
    const message = (textarea.value || "").trim();
    if (!message) return;
    try {
      const detail = await api(`/api/v1/admin/messages/threads/${activeId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      textarea.value = "";
      renderChat(detail);
      await loadThreads();
      await loadUnreadBadge();
    } catch (err) {
      alert(err.message);
    }
  });

  refreshBtn.addEventListener("click", () => {
    loadThreads().catch((err) => alert(err.message));
    loadUnreadBadge();
    if (activeId) openThread(activeId).catch(() => {});
  });

  unreadOnly.addEventListener("change", () => loadThreads().catch((err) => alert(err.message)));

  function startPoll() {
    stopPoll();
    pollTimer = setInterval(() => {
      loadThreads().catch(() => {});
      loadUnreadBadge();
      if (activeId) openThread(activeId).catch(() => {});
    }, 5000);
  }

  function stopPoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopPoll();
    else startPoll();
  });

  loadThreads().catch((err) => {
    threadsEl.innerHTML = `<p class="hint">${esc(err.message)}</p>`;
  });
  loadUnreadBadge();
  startPoll();
})();
