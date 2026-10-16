// The Copy button next to the install line. Without JavaScript the line is
// still there to select by hand.
document.querySelectorAll("button.copy").forEach((button) => {
  const label = button.textContent;
  button.addEventListener("click", async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Select it by hand";
    }
    setTimeout(() => { button.textContent = label; }, 2500);
  });
});
