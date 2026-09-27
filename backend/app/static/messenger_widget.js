(function () {
  const API = "/api/v1/messages";

  const MESSENGER_MOCKS = [
    {
      id: "telegram",
      label: "Telegram",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8-1.55 7.3c-.12.54-.43.67-.87.42l-2.4-1.77-1.16 1.12c-.13.13-.24.24-.49.24l.17-2.43 4.42-4c.19-.17-.04-.27-.3-.1l-5.46 3.44-2.35-.74c-.51-.16-.52-.51.11-.76l9.18-3.54c.42-.17.79.1.6.82z"/></svg>',
    },
    {
      id: "whatsapp",
      label: "WhatsApp",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.86 9.86 0 0 0 12.04 2zm0 1.82c4.46 0 8.09 3.63 8.09 8.09 0 4.46-3.63 8.09-8.09 8.09-1.42 0-2.8-.37-4.01-1.07l-.29-.17-3.12.82.83-3.04-.19-.31a8.05 8.05 0 0 1-1.23-4.32c0-4.46 3.63-8.09 8.01-8.09zm4.61 10.5c-.25-.13-1.48-.73-1.71-.81-.23-.09-.4-.13-.56.13-.17.25-.64.81-.79.98-.14.17-.29.19-.54.06-.25-.13-1.05-.39-2-1.23-.74-.66-1.24-1.48-1.39-1.73-.14-.25-.02-.39.11-.51.11-.11.25-.29.37-.43.13-.14.17-.25.25-.42.09-.17.04-.31-.02-.44-.06-.13-.56-1.35-.77-1.85-.2-.48-.41-.42-.56-.42h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.09 0 1.23.9 2.42 1.02 2.59.13.17 1.77 2.7 4.29 3.79.6.26 1.07.41 1.43.53.6.19 1.15.16 1.58.1.48-.07 1.48-.61 1.69-1.19.21-.59.21-1.09.14-1.19-.06-.11-.23-.17-.48-.3z"/></svg>',
    },
    {
      id: "viber",
      label: "Viber",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11.4 2.01C6.53 2.2 2.8 5.8 2.4 10.7c-.25 3.15.95 6 3.35 7.85v2.9l2.85-1.55c.95.25 1.95.4 2.95.35 4.95-.2 8.85-4.25 8.85-9.2 0-5.15-4.35-9.2-9-8.04zm.2 1.8c3.85 0 7.05 3.1 7.05 7 0 3.9-3.2 7.15-7.2 7.3-.9.05-1.75-.1-2.55-.35l-.45-.15-1.7.95v-1.8l-.3-.2c-1.9-1.4-3-3.55-2.8-5.9.35-3.85 3.5-6.85 7.95-6.85zm1.35 2.55c-.2 0-.4.05-.55.25-.2.25-.75.9-.75 2.2s.8 2.55.9 2.75c.1.2 1.55 2.5 3.85 3.4 1.9.75 2.3.6 2.7.55.4-.05 1.3-.55 1.5-1.05.2-.5.2-.95.15-1.05-.05-.1-.2-.15-.4-.25-.2-.1-1.25-.6-1.45-.7-.2-.1-.35-.15-.5.15-.15.25-.55.7-.7.85-.15.15-.25.2-.45.05-.2-.15-.85-.3-1.65-1-.6-.55-1.05-1.2-1.15-1.4-.1-.2 0-.3.1-.4.1-.1.2-.25.3-.35.1-.1.15-.2.2-.35.05-.15 0-.25-.05-.35-.05-.1-.5-1.2-.7-1.65-.15-.4-.35-.35-.5-.35z"/></svg>',
    },
    {
      id: "max",
      label: "MAX",
      svg: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm3.7 13.55h-1.72l-1.18-3.74h-.05l-1.2 3.74H9.83L7.55 8.45h1.8l1.12 3.9h.05l1.2-3.9h1.6l1.2 3.9h.05l1.12-3.9h1.76l-2.35 7.1z"/></svg>',
    },
  ];

  function messengersBlockHtml() {
    const buttons = MESSENGER_MOCKS.map(
      (m) =>
        `<button type="button" class="a160-msg-external-btn" data-messenger-mock="${m.id}" data-messenger="${m.id}" aria-label="${m.label}">
          ${m.svg}<span>${m.label}</span>
        </button>`
    ).join("");
    return `<div class="a160-msg-external" data-a160-msg-external>
      <p class="a160-msg-external-title">Или напишите в мессенджере</p>
      <div class="a160-msg-external-row" role="group" aria-label="Мессенджеры">${buttons}</div>
      <p class="a160-msg-external-hint">Ссылки скоро появятся — пока демо-кнопки.</p>
    </div>`;
  }

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
          ${messengersBlockHtml()}
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
          ${messengersBlockHtml()}
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

  root.addEventListener("click", (event) => {
    const mockBtn = event.target.closest("[data-messenger-mock]");
    if (!mockBtn) return;
    event.preventDefault();
    const name = mockBtn.getAttribute("data-messenger-mock") || "мессенджер";
    alert(`Ссылка на ${name} пока не подключена (мок).`);
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
