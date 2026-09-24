(function () {
  function bindSwipe(target, onSwipe) {
    if (!target || typeof onSwipe !== "function") return;
    var startX = 0;
    var startY = 0;
    var moved = false;
    var swiped = false;

    target.addEventListener(
      "touchstart",
      function (event) {
        if (!event.touches || !event.touches.length) return;
        startX = event.touches[0].clientX;
        startY = event.touches[0].clientY;
        moved = false;
        swiped = false;
      },
      { passive: true }
    );

    target.addEventListener(
      "touchmove",
      function (event) {
        if (!event.touches || !event.touches.length) return;
        var dx = event.touches[0].clientX - startX;
        var dy = event.touches[0].clientY - startY;
        if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy)) {
          moved = true;
          // Keep the page from rubber-banding horizontally while swiping photos.
          if (event.cancelable) event.preventDefault();
        }
      },
      { passive: false }
    );

    target.addEventListener(
      "touchend",
      function (event) {
        if (!moved) return;
        var touch = event.changedTouches && event.changedTouches[0];
        if (!touch) return;
        var dx = touch.clientX - startX;
        if (Math.abs(dx) < 40) return;
        swiped = true;
        onSwipe(dx < 0 ? 1 : -1);
      },
      { passive: true }
    );

    target.addEventListener(
      "click",
      function (event) {
        if (!swiped) return;
        event.preventDefault();
        event.stopPropagation();
        swiped = false;
      },
      true
    );
  }

  document.querySelectorAll("[data-listings-feed-gallery]").forEach(function (gallery) {
    var raw = gallery.getAttribute("data-photo-urls");
    if (!raw) return;

    var urls;
    try {
      urls = JSON.parse(raw);
    } catch (error) {
      return;
    }
    if (!Array.isArray(urls) || urls.length <= 1) return;

    var img = gallery.querySelector("[data-listings-feed-gallery-photo]");
    var prevBtn = gallery.querySelector(".listings-feed-gallery-prev");
    var nextBtn = gallery.querySelector(".listings-feed-gallery-next");
    if (!img) return;

    var index = 0;

    function showPhoto(nextIndex) {
      index = (nextIndex + urls.length) % urls.length;
      img.src = urls[index];
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        showPhoto(index - 1);
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        showPhoto(index + 1);
      });
    }

    bindSwipe(gallery, function (step) {
      showPhoto(index + step);
    });
  });
})();
