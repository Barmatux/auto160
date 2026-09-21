/**
 * Auto160 public chat widget — floating panel calling POST /api/v1/chat.
 */
(function () {
  "use strict";

  if (location.pathname.indexOf("/admin") === 0) return;

  var SESSION_KEY = "auto160_chat_session";
  var HISTORY_KEY = "auto160_chat_history";

  function sessionId() {
    try {
      var id = localStorage.getItem(SESSION_KEY);
      if (id) return id;
      id = "s" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(SESSION_KEY, id);
      return id;
    } catch (e) {
      return null;
    }
  }

  function loadHistory() {
    try {
      var raw = sessionStorage.getItem(HISTORY_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(-8) : [];
    } catch (e) {
      return [];
    }
  }

  function saveHistory(items) {
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(-8)));
    } catch (e) {
      /* ignore */
    }
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function linkify(text) {
    var frag = document.createDocumentFragment();
    var re = /(\/(?:listings|catalog|guides|inspection)[^\s]*)|(https?:\/\/auto160\.(?:ru|by)[^\s]*)/g;
    var last = 0;
    var m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      var a = document.createElement("a");
      a.href = m[0];
      a.textContent = m[0];
      a.rel = "noopener";
      frag.appendChild(a);
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    return frag;
  }

  var root = el("div", "a160-chat");
  root.setAttribute("data-a160-chat", "");

  var toggle = el("button", "a160-chat-toggle", "Помощник");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "a160-chat-panel");

  var panel = el("div", "a160-chat-panel");
  panel.id = "a160-chat-panel";
  panel.hidden = true;

  var head = el("div", "a160-chat-head");
  head.appendChild(el("strong", null, "Помощник Auto160"));
  var closeBtn = el("button", "a160-chat-close", "×");
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "Закрыть");
  head.appendChild(closeBtn);

  var messages = el("div", "a160-chat-messages");
  messages.setAttribute("role", "log");
  messages.setAttribute("aria-live", "polite");

  var intro = el("div", "a160-chat-msg a160-chat-msg-bot");
  intro.appendChild(
    linkify(
      "Спросите про авто до 160 л.с., VIN, каталог или объявления — например «Skoda Octavia до 15000 BYN в Минске»."
    )
  );
  messages.appendChild(intro);

  var form = el("form", "a160-chat-form");
  var input = document.createElement("textarea");
  input.className = "a160-chat-input";
  input.rows = 2;
  input.maxLength = 2000;
  input.placeholder = "Ваш вопрос…";
  input.setAttribute("aria-label", "Сообщение помощнику");
  var send = el("button", "a160-chat-send", "Отправить");
  send.type = "submit";
  form.appendChild(input);
  form.appendChild(send);

  panel.appendChild(head);
  panel.appendChild(messages);
  panel.appendChild(form);
  root.appendChild(panel);
  root.appendChild(toggle);
  document.body.appendChild(root);

  var history = loadHistory();
  var busy = false;
  var enabled = true;

  function setOpen(open) {
    if (open) {
      panel.removeAttribute("hidden");
    } else {
      panel.setAttribute("hidden", "");
    }
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    root.classList.toggle("is-open", open);
    if (open) input.focus();
  }

  toggle.addEventListener("click", function () {
    setOpen(panel.hasAttribute("hidden"));
  });
  closeBtn.addEventListener("click", function (ev) {
    ev.preventDefault();
    ev.stopPropagation();
    setOpen(false);
  });

  function appendMessage(role, text, citations) {
    var row = el("div", "a160-chat-msg a160-chat-msg-" + (role === "user" ? "user" : "bot"));
    if (role === "user") {
      row.textContent = text;
    } else {
      row.appendChild(linkify(text));
      if (citations && citations.length) {
        var cites = el("div", "a160-chat-cites");
        citations.forEach(function (c) {
          var a = document.createElement("a");
          a.href = c.url;
          a.textContent = c.title;
          cites.appendChild(a);
        });
        row.appendChild(cites);
      }
    }
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  fetch("/api/v1/chat/status")
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (!data || !data.enabled) {
        enabled = false;
        root.hidden = true;
      }
    })
    .catch(function () {
      /* keep widget; send will surface errors */
    });

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (busy || !enabled) return;
    var text = (input.value || "").trim();
    if (!text) return;

    appendMessage("user", text);
    input.value = "";
    busy = true;
    send.disabled = true;

    var pending = el("div", "a160-chat-msg a160-chat-msg-bot a160-chat-pending", "Думаю…");
    messages.appendChild(pending);
    messages.scrollTop = messages.scrollHeight;

    var payload = {
      message: text,
      history: history,
      session_id: sessionId(),
    };

    fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, status: r.status, data: data };
        });
      })
      .then(function (res) {
        pending.remove();
        if (!res.ok) {
          var detail =
            (res.data && (res.data.detail || res.data.message)) ||
            "Не удалось получить ответ (" + res.status + ")";
          if (typeof detail === "object") detail = JSON.stringify(detail);
          appendMessage("bot", String(detail));
          return;
        }
        var answer = (res.data && res.data.answer) || "";
        var citations = (res.data && res.data.citations) || [];
        appendMessage("bot", answer, citations);
        history.push({ role: "user", content: text });
        history.push({ role: "assistant", content: answer });
        history = history.slice(-8);
        saveHistory(history);
      })
      .catch(function () {
        pending.remove();
        appendMessage("bot", "Сеть недоступна. Попробуйте ещё раз.");
      })
      .finally(function () {
        busy = false;
        send.disabled = false;
      });
  });

  input.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });
})();
