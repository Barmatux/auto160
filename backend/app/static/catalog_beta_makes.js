(function () {
  const button = document.getElementById("catalog-beta-next-btn");
  const checkboxes = Array.from(document.querySelectorAll(".catalog-make-checkbox"));
  if (!button) return;

  button.addEventListener("click", () => {
    const params = new URLSearchParams();
    checkboxes
      .filter((cb) => cb.checked)
      .forEach((cb) => params.append("make", cb.value));
    const query = params.toString();
    window.location.href = query ? "/catalog/beta/models?" + query : "/catalog/beta/models";
  });
})();
