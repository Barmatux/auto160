(function () {
  const API = "/api/v1/messages";

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function api(path, opts) {
    const response = await fetch(API + path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opts,
    });
    if (!response.ok) {
      let detail = "Ошибка запроса";
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function ensureUi() {
    if (document.querySelector("[data-a160-messenger]")) return;
    const root = document.createElement("div");
    root.className = "a160-msg";
    root.setAttribute("data-a160-messenger", "");
    root.innerHTML = `
      <button type="button" class="a160-msg-fab" data-a160-msg-fab aria-label="Сообщения">
        <span class="a160-msg-fab-icon" aria-hidden="true">💬</span>
        <span class="a160-msg-fab-badge" data-a160-msg-badge hidden>0</span>
      </button>
      <div class="a160-msg-panel" data-a160-msg-panel hidden>
        <header class="a160-msg-panel-header">
          <button type="button" class="a160-msg-back" data-a160-msg-back hidden>←</button>
          <strong data-a160-msg-title>Сообщения</strong>
          <button type="button" class="a160-msg-close" data-a160-msg-close aria-label="Закрыть">×</button>
        </header>
        <div class="a160-msg-list" data-a160-msg-list></div>
        <div class="a160-msg-chat" data-a160-msg-chat hidden>
          <div class="a160-msg-messages" data-a160-msg-messages></div>
          <form class="a160-msg-compose" data-a160-msg-compose>
            <textarea name="message" rows="2" maxlength="4000" placeholder="Ваше сообщение…" required></textarea>
            <button type="submit">Отправить</button>
          </form>
        </div>
      </div>
      <div class="a160-msg-modal" data-a160-msg-modal hidden>
        <div class="a160-msg-modal-card">
          <h3>Написать менеджеру</h3>
          <p class="hint">Менеджер Auto160 ответит в этом чате. Регистрация не нужна.</p>
          <form data-a160-msg-start-form>
            <label>Имя<input name="name" required maxlength="120" autocomplete="name" /></label>
            <label>Телефон<input name="phone" required maxlength="40" autocomplete="tel" /></label>
            <label>Сообщение<textarea name="message" rows="4" required maxlength="4000" placeholder="Здравствуйте! Интересует это авто…"></textarea></label>
            <p class="a160-msg-error" data-a160-msg-error hidden></p>
            <div class="a160-msg-modal-actions">
              <button type="button" class="btn-secondary" data-a160-msg-modal-cancel>Отмена</button>
              <button type="submit" class="btn-primary">Отправить</button>
            </div>
          </form>
        </div>
      </div>
    `;
    document.body.appendChild(root);
  }

  ensureUi();
  const root = document.querySelector("[data-a160-messenger]");
  const fab = root.querySelector("[data-a160-msg-fab]");
  const badge = root.querySelector("[data-a160-msg-badge]");
  const panel = root.querySelector("[data-a160-msg-panel]");
  const listEl = root.querySelector("[data-a160-msg-list]");
  const chatEl = root.querySelector("[data-a160-msg-chat]");
  const messagesEl = root.querySelector("[data-a160-msg-messages]");
  const compose = root.querySelector("[data-a160-msg-compose]");
  const titleEl = root.querySelector("[data-a160-msg-title]");
  const backBtn = root.querySelector("[data-a160-msg-back]");
  const closeBtn = root.querySelector("[data-a160-msg-close]");
  const modal = root.querySelector("[data-a160-msg-modal]");
  const startForm = root.querySelector("[data-a160-msg-start-form]");
  const startError = root.querySelector("[data-a160-msg-error]");
  const modalCancel = root.querySelector("[data-a160-msg-modal-cancel]");

  let activeThreadId = null;
  let pendingListingId = null;
  let pollTimer = null;
  let panelOpen = false;

  function setBadge(count) {
    if (count > 0) {
      badge.hidden = false;
      badge.textContent = String(count);
      fab.classList.add("has-unread");
    } else {
      badge.hidden = true;
      fab.classList.remove("has-unread");
    }
  }

  async function refreshBadge() {
    try {
      const data = await api("/unread-count");
      setBadge(data.count || 0);
    } catch (_) {}
  }

  function showList() {
    activeThreadId = null;
    backBtn.hidden = true;
    titleEl.textContent = "Сообщения";
    chatEl.hidden = true;
    listEl.hidden = false;
  }

  function renderList(items) {
    if (!items.length) {
      listEl.innerHTML = '<p class="hint a160-msg-empty">Пока нет диалогов. Напишите менеджеру с карточки объявления.</p>';
      return;
    }
    listEl.innerHTML = items
      .map((t) => {
        const unread = t.unread_count > 0 ? `<span class="a160-msg-pill">${t.unread_count}</span>` : "";
        return `<button type="button" class="a160-msg-row" data-thread-id="${t.id}">
          <div class="a160-msg-row-title">${esc(t.listing_title)} ${unread}</div>
          <div class="a160-msg-row-preview">${esc(t.last_preview || "")}</div>
        </button>`;
      })
      .join("");
  }

  function renderMessages(detail) {
    messagesEl.innerHTML = detail.messages
      .map((m) => {
        const side = m.sender === "visitor" ? "me" : "them";
        const when = new Date(m.created_at).toLocaleString("ru-RU");
        return `<div class="a160-msg-bubble a160-msg-bubble-${side}">
          <div class="a160-msg-bubble-body">${esc(m.body)}</div>
          <div class="a160-msg-bubble-meta">${esc(when)}</div>
        </div>`;
      })
      .join("");
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function loadList() {
    const items = await api("/threads");
    renderList(items);
    return items;
  }

  async function openThread(id) {
    const detail = await api(`/threads/${id}`);
    activeThreadId = id;
    listEl.hidden = true;
    chatEl.hidden = false;
    backBtn.hidden = false;
    titleEl.textContent = detail.listing_title;
    renderMessages(detail);
    await refreshBadge();
  }

  function openPanel() {
    panel.hidden = false;
    panelOpen = true;
    showList();
    loadList().catch(() => {
      listEl.innerHTML = '<p class="hint">Не удалось загрузить диалоги</p>';
    });
    startPoll();
  }

  function closePanel() {
    panel.hidden = true;
    panelOpen = false;
    stopPoll();
  }

  function openModal(listingId) {
    pendingListingId = listingId;
    startError.hidden = true;
    startForm.reset();
    const defaultMsg = "Здравствуйте! Интересует это объявление. Подскажите, пожалуйста, актуальные детали.";
    startForm.querySelector('[name="message"]').value = defaultMsg;
    modal.hidden = false;
  }

  function closeModal() {
    modal.hidden = true;
    pendingListingId = null;
  }

  fab.addEventListener("click", () => {
    if (panelOpen) closePanel();
    else openPanel();
  });
  closeBtn.addEventListener("click", closePanel);
  backBtn.addEventListener("click", () => {
    showList();
    loadList().catch(() => {});
  });
  modalCancel.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  listEl.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-thread-id]");
    if (!btn) return;
    openThread(Number(btn.getAttribute("data-thread-id"))).catch((err) => alert(err.message));
  });

  compose.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!activeThreadId) return;
    const textarea = compose.querySelector("textarea");
    const message = (textarea.value || "").trim();
    if (!message) return;
    try {
      const detail = await api(`/threads/${activeThreadId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      textarea.value = "";
      renderMessages(detail);
    } catch (err) {
      alert(err.message);
    }
  });

  startForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!pendingListingId) return;
    const fd = new FormData(startForm);
    startError.hidden = true;
    try {
      const detail = await api("/threads", {
        method: "POST",
        body: JSON.stringify({
          listing_id: pendingListingId,
          name: String(fd.get("name") || ""),
          phone: String(fd.get("phone") || ""),
          message: String(fd.get("message") || ""),
        }),
      });
      closeModal();
      openPanel();
      await openThread(detail.id);
      await refreshBadge();
    } catch (err) {
      startError.hidden = false;
      startError.textContent = err.message || "Не удалось отправить";
    }
  });

  document.addEventListener("click", (event) => {
    const startBtn = event.target.closest("[data-messenger-start]");
    if (!startBtn) return;
    const cta = startBtn.closest("[data-listing-contact-cta]");
    const listingId = Number(cta && cta.getAttribute("data-listing-id"));
    if (!listingId) return;
    openModal(listingId);
  });

  function startPoll() {
    stopPoll();
    pollTimer = setInterval(() => {
      if (!panelOpen || document.hidden) return;
      refreshBadge();
      if (activeThreadId) {
        openThread(activeThreadId).catch(() => {});
      } else {
        loadList().catch(() => {});
      }
    }, 5000);
  }

  function stopPoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  refreshBadge();
})();
