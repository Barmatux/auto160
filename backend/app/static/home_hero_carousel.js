/* Compact hero uses native CSS scroll-snap; no deck animation. */
(function () {
  var root = document.querySelector("[data-home-hero-carousel]");
  if (!root) return;
  root.classList.remove("home-hero-split--deck");
  root.querySelectorAll(".home-hero-pane").forEach(function (pane) {
    pane.classList.remove("is-front", "is-back");
    pane.removeAttribute("aria-hidden");
  });
})();
