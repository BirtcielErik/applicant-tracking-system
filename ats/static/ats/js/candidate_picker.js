const picker = document.querySelector("[data-candidate-picker]");
const chosen = picker.querySelector('input[type="hidden"]');
const search = picker.querySelector('input[type="search"]');
const results = picker.querySelector("ul");

function showResults() {
  results.classList.remove("hidden");
}

function hideResults() {
  results.classList.add("hidden");
}

function choose(option) {
  chosen.value = option.dataset.value;
  search.value = option.dataset.label;
  hideResults();
}

search.addEventListener("focus", showResults);

search.addEventListener("input", () => {
  // Editing the text abandons the earlier choice, so it cannot be saved unseen.
  chosen.value = "";
  showResults();
});

search.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hideResults();
  } else if (event.key === "Enter") {
    // Enter picks the top match instead of submitting a half-finished form.
    event.preventDefault();
    const option = results.querySelector("button");
    if (option) {
      choose(option);
    }
  }
});

results.addEventListener("click", (event) => {
  const option = event.target.closest("button");
  if (option) {
    choose(option);
  }
});

document.addEventListener("click", (event) => {
  if (!picker.contains(event.target)) {
    hideResults();
  }
});
