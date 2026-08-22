(function () {
  var toggle = document.querySelector("[data-header-menu-toggle]");
  var nav = document.querySelector("[data-header-nav]");
  if (!toggle || !nav) return;

  function setOpen(open) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    nav.classList.toggle("is-open", open);
    document.body.classList.toggle("header-nav-open", open);
  }

  toggle.addEventListener("click", function () {
    setOpen(!nav.classList.contains("is-open"));
  });

  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      setOpen(false);
      closeAllDropdowns();
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setOpen(false);
      closeAllDropdowns();
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 900) {
      setOpen(false);
    }
  });

  var dropdowns = Array.prototype.slice.call(document.querySelectorAll("[data-header-dropdown]"));

  function closeAllDropdowns(except) {
    dropdowns.forEach(function (dropdown) {
      if (except && dropdown === except) return;
      dropdown.classList.remove("is-open");
      var menu = dropdown.querySelector("[data-header-dropdown-menu]");
      var button = dropdown.querySelector("[data-header-dropdown-toggle]");
      if (menu) menu.hidden = true;
      if (button) button.setAttribute("aria-expanded", "false");
    });
  }

  dropdowns.forEach(function (dropdown) {
    var button = dropdown.querySelector("[data-header-dropdown-toggle]");
    var menu = dropdown.querySelector("[data-header-dropdown-menu]");
    if (!button || !menu) return;

    button.addEventListener("click", function (event) {
      event.stopPropagation();
      var willOpen = menu.hidden;
      closeAllDropdowns(willOpen ? dropdown : null);
      menu.hidden = !willOpen;
      dropdown.classList.toggle("is-open", willOpen);
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  });

  document.addEventListener("click", function () {
    closeAllDropdowns();
  });

  var path = window.location.pathname;
  nav.querySelectorAll("a[href]").forEach(function (link) {
    var href = link.getAttribute("href");
    if (!href || href.charAt(0) !== "/") return;
    if (path === href || (href !== "/" && path.indexOf(href) === 0)) {
      link.classList.add("is-active");
      var parentDropdown = link.closest("[data-header-dropdown]");
      if (parentDropdown) {
        parentDropdown.classList.add("is-active");
      }
    }
  });
})();
