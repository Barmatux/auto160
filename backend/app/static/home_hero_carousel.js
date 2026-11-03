(function () {
  var root = document.querySelector("[data-home-hero-carousel]");
  if (!root) return;

  var mq = window.matchMedia("(max-width: 1100px)");
  var panes = Array.prototype.slice.call(root.querySelectorAll(".home-hero-pane"));
  if (panes.length < 2) return;

  var index = 0;
  var startX = 0;
  var startY = 0;
  var tracking = false;
  var locked = false;

  function apply() {
    if (!mq.matches) {
      root.classList.remove("home-hero-split--deck");
      panes.forEach(function (pane) {
        pane.classList.remove("is-front", "is-back");
      });
      return;
    }
    root.classList.add("home-hero-split--deck");
    panes.forEach(function (pane, i) {
      var front = i === index;
      pane.classList.toggle("is-front", front);
      pane.classList.toggle("is-back", !front);
      pane.setAttribute("aria-hidden", front ? "false" : "true");
    });
  }

  function go(next) {
    if (!mq.matches || locked) return;
    var len = panes.length;
    index = ((next % len) + len) % len;
    locked = true;
    apply();
    window.setTimeout(function () {
      locked = false;
    }, 380);
  }

  root.addEventListener(
    "touchstart",
    function (event) {
      if (!mq.matches || event.touches.length !== 1) return;
      tracking = true;
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
    },
    { passive: true }
  );

  root.addEventListener(
    "touchend",
    function (event) {
      if (!tracking) return;
      tracking = false;
      var touch = event.changedTouches[0];
      if (!touch) return;
      var dx = touch.clientX - startX;
      var dy = touch.clientY - startY;
      if (Math.abs(dx) < 42 || Math.abs(dx) < Math.abs(dy)) return;
      if (dx < 0) go(index + 1);
      else go(index - 1);
    },
    { passive: true }
  );

  panes.forEach(function (pane, i) {
    pane.addEventListener("click", function (event) {
      if (!mq.matches || i === index) return;
      // Tap the peeking card to bring it forward.
      event.preventDefault();
      go(i);
    });
  });

  if (typeof mq.addEventListener === "function") {
    mq.addEventListener("change", apply);
  } else if (typeof mq.addListener === "function") {
    mq.addListener(apply);
  }

  apply();
})();
