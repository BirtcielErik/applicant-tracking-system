function initBoard() {
  const board = document.getElementById("board");
  board.querySelectorAll("[data-stage]").forEach((column) => {
    Sortable.create(column, {
      group: "pipeline",
      sort: false,
      animation: 150,
      onEnd(event) {
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

initBoard();
document.addEventListener("htmx:afterSwap", initBoard);
// A failed request swaps nothing, so reload to put the dragged card back.
document.addEventListener("htmx:responseError", () => location.reload());
