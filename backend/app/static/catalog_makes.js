(function () {
  const button = document.getElementById("go-to-models-btn");
  const checkboxes = Array.from(document.querySelectorAll(".catalog-make-checkbox"));
  if (!button || !checkboxes.length) return;

  const root = document.querySelector(".catalog-page");
  const filterQuery = root?.dataset.catalogFilterQuery || "";

  function syncButton() {
    const selected = checkboxes.filter((cb) => cb.checked);
    button.disabled = selected.length === 0;
  }

  checkboxes.forEach((cb) => cb.addEventListener("change", syncButton));

  button.addEventListener("click", () => {
    const selected = checkboxes.filter((cb) => cb.checked).map((cb) => cb.value);
    if (!selected.length) return;
    const params = new URLSearchParams(filterQuery);
    selected.forEach((make) => params.append("make", make));
    window.location.href = "/catalog/models?" + params.toString();
  });

  syncButton();
})();
