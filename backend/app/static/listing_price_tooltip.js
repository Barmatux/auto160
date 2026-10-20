(function () {
  var VIEWPORT_PAD = 12;
  var GAP = 8;

  function stickyHeaderBottom() {
    var header = document.querySelector("body > .header");
    if (!header) return VIEWPORT_PAD;
    var rect = header.getBoundingClientRect();
    // Only reserve space while the site header is sticking at the top.
    if (rect.bottom <= 0) return VIEWPORT_PAD;
    return Math.max(VIEWPORT_PAD, Math.ceil(rect.bottom) + GAP);
  }

  function getTip(priceEl) {
    return priceEl._priceTooltipEl || priceEl.querySelector(".listing-price-tooltip");
  }

  function mountTipToBody(priceEl, tip) {
    if (!tip || tip.parentElement === document.body) return;
    priceEl._priceTooltipEl = tip;
    tip._priceTooltipHome = priceEl;
    document.body.appendChild(tip);
  }

  function restoreTip(priceEl, tip) {
    if (!tip) return;
    var home = tip._priceTooltipHome || priceEl;
    if (home && tip.parentElement === document.body) {
      home.appendChild(tip);
    }
    tip._priceTooltipHome = null;
    priceEl._priceTooltipEl = null;
  }

  function placeTooltip(priceEl) {
    var tip = getTip(priceEl);
    if (!tip) return;

    // Reparent to body so card hover `transform` does not create a containing
    // block for position:fixed (breaks placement in 2nd/3rd grid columns).
    mountTipToBody(priceEl, tip);

    tip.style.position = "fixed";
    tip.style.left = "0";
    tip.style.top = "0";
    tip.style.right = "auto";
    tip.style.bottom = "auto";
    tip.style.transform = "none";
    tip.style.width = "";
    tip.style.maxWidth = "";
    tip.style.zIndex = "1200";
    tip.style.visibility = "hidden";
    tip.style.display = "block";

    var anchor = priceEl.getBoundingClientRect();
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var maxWidth = Math.min(360, vw - VIEWPORT_PAD * 2);
    tip.style.width = maxWidth + "px";
    tip.style.maxWidth = maxWidth + "px";

    var tipRect = tip.getBoundingClientRect();
    var tipW = tipRect.width;
    var tipH = tipRect.height;
    var minTop = stickyHeaderBottom();

    var spaceBelow = vh - anchor.bottom - VIEWPORT_PAD;
    var spaceAbove = anchor.top - minTop;
    var placeBelow = spaceBelow >= tipH + GAP || spaceBelow >= spaceAbove;

    var top = placeBelow
      ? anchor.bottom + GAP
      : anchor.top - tipH - GAP;
    top = Math.max(minTop, Math.min(top, vh - tipH - VIEWPORT_PAD));

    var left = anchor.left;
    if (priceEl.closest(".listing-detail-header-price")) {
      left = anchor.right - tipW;
    }
    left = Math.max(VIEWPORT_PAD, Math.min(left, vw - tipW - VIEWPORT_PAD));

    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
    tip.style.visibility = "visible";
  }

  function clearTooltip(priceEl) {
    var tip = getTip(priceEl);
    if (!tip) return;
    tip.style.display = "";
    tip.style.visibility = "";
    tip.style.position = "";
    tip.style.left = "";
    tip.style.top = "";
    tip.style.right = "";
    tip.style.bottom = "";
    tip.style.transform = "";
    tip.style.width = "";
    tip.style.maxWidth = "";
    tip.style.zIndex = "";
    restoreTip(priceEl, tip);
  }

  function bindPriceTooltips(root) {
    root.querySelectorAll(".listing-price-has-conversions").forEach(function (priceEl) {
      if (priceEl.dataset.priceTooltipBound === "1") {
        return;
      }
      priceEl.dataset.priceTooltipBound = "1";

      var show = function () {
        placeTooltip(priceEl);
        priceEl.classList.add("is-price-tooltip-open");
      };
      var hide = function () {
        priceEl.classList.remove("is-price-tooltip-open");
        clearTooltip(priceEl);
      };
      var reposition = function () {
        if (priceEl.classList.contains("is-price-tooltip-open")) {
          placeTooltip(priceEl);
        }
      };

      priceEl.addEventListener("mouseenter", show);
      priceEl.addEventListener("mouseleave", hide);
      priceEl.addEventListener("focusin", show);
      priceEl.addEventListener("focusout", function (event) {
        if (!priceEl.contains(event.relatedTarget)) {
          hide();
        }
      });
      window.addEventListener("resize", reposition);
      window.addEventListener("scroll", reposition, true);
    });
  }

  bindPriceTooltips(document);
  document.addEventListener("DOMContentLoaded", function () {
    bindPriceTooltips(document);
  });
})();
