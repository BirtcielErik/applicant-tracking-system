function initBoard() {
  const board = document.getElementById("board");
  board.querySelectorAll("[data-stage]").forEach((column) => {
    Sortable.create(column, {
      group: "pipeline",
      sort: false,
      animation: 150,
      onStart(event) {
        const allowed = event.item.dataset.allowedStages.split(" ");
        board.querySelectorAll("[data-stage]").forEach((target) => {
          if (target === event.from) return;
          target.closest("section").dataset.drop = allowed.includes(
            target.dataset.stage,
          )
            ? "allowed"
            : "blocked";
        });
      },
      onEnd(event) {
        board.querySelectorAll("[data-drop]").forEach((section) => {
          delete section.dataset.drop;
        });
        if (event.from === event.to) return;
        htmx.ajax("POST", event.item.dataset.moveUrl, {
          target: board,
          swap: "innerHTML",
          headers: { "X-CSRFToken": board.dataset.csrfToken },
          values: { stage: event.to.dataset.stage },
        });
      },
    });
  });
}

function dismissMoveError() {
  const toast = document.querySelector("[data-move-error]");
  if (toast) setTimeout(() => toast.remove(), 5000);
}

initBoard();
document.addEventListener("htmx:afterSwap", () => {
  initBoard();
  dismissMoveError();
});
// A failed request swaps nothing, so reload to put the dragged card back.
document.addEventListener("htmx:responseError", () => location.reload());
