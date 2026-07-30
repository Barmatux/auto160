(function () {
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
    if (!img || !prevBtn || !nextBtn) return;

    var index = 0;

    function showPhoto(nextIndex) {
      index = (nextIndex + urls.length) % urls.length;
      img.src = urls[index];
    }

    prevBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      showPhoto(index - 1);
    });

    nextBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      showPhoto(index + 1);
    });
  });
})();
