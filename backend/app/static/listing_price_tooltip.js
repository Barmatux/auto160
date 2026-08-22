(function () {
  function bindPriceTooltips(root) {
    root.querySelectorAll(".listing-price-has-conversions").forEach(function (priceEl) {
      if (priceEl.dataset.priceTooltipBound === "1") {
        return;
      }
      priceEl.dataset.priceTooltipBound = "1";

      var show = function () {
        priceEl.classList.add("is-price-tooltip-open");
      };
      var hide = function () {
        priceEl.classList.remove("is-price-tooltip-open");
      };

      priceEl.addEventListener("mouseenter", show);
      priceEl.addEventListener("mouseleave", hide);
      priceEl.addEventListener("focusin", show);
      priceEl.addEventListener("focusout", hide);
    });
  }

  bindPriceTooltips(document);
  document.addEventListener("DOMContentLoaded", function () {
    bindPriceTooltips(document);
  });
})();
